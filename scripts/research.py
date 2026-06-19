#!/usr/bin/env python3
"""research.py — LLM Researcher with web access (Brave + fetch MCP).

Stage 0 of the creative chain. Takes a SEED (+ format + channel context) and produces a
sourced research brief the script writer + reviewers consume. UNLIKE llm_call.py (which
trusts NO tools), the researcher MUST use web tools, so it has its own kiro-cli invocation
that trusts brave + fetch. It is instructed to ground every claim in real, citable primary
sources and to reply NO_WEB_TOOL (failing loudly) rather than fabricate if no tool is available.

Sourcing non-negotiable: >=3 independent primary sources; TED/popular = trend input only;
each claim carries a citation (title, author/site, year, URL).

Output: research_brief.json {seed, angle, key_claims[{claim, source{title,url,year}}],
research_text, sources[], suggested_titles[]}.

Usage (run by the orchestrator; long-running, timeout-bounded — never inline):
  python3 scripts/research.py "using AI to help memory retention" --format short \
      --output <dir>/research_brief.json --transcript <dir>/research.md
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
KIRO = "kiro-cli"
import os
import urllib.parse
import urllib.request

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Curated reputable source domains. Results from these are prioritized.
REPUTABLE_DOMAINS = [
    "nature.com", "science.org", "sciencedirect.com", "springer.com", "wiley.com",
    "tandfonline.com", "sagepub.com", "pnas.org", "jstor.org", "arxiv.org", "ssrn.com",
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "researchgate.net", "acm.org", "ieee.org",
    ".edu", "ox.ac.uk", "cam.ac.uk",
    "hbr.org", "sloanreview.mit.edu", "mckinsey.com", "bcg.com", "deloitte.com",
    "economist.com", "ft.com", "hbsp.harvard.edu",
    "technologyreview.com", "deepmind.com", "openai.com",
    "ai.googleblog.com", "research.google", "microsoft.com/en-us/research",
    "anthropic.com", "hai.stanford.edu",
    "london.edu", "insead.edu", "lbs.edu",
]

MAX_RESULTS_FOR_PROMPT = 25


def _is_reputable(url):
    """Return True if url matches any REPUTABLE_DOMAINS entry."""
    if not url:
        return False
    url_lower = url.lower()
    for domain in REPUTABLE_DOMAINS:
        if domain in url_lower:
            return True
    return False


def _brave_key():
    """Read the Brave API key from env or the gitignored runtime env (never hardcode)."""
    key = os.environ.get("BRAVE_API_KEY")
    if key:
        return key
    # fall back to the mcp.json env (already on this machine) so the researcher has a key
    import json as _json
    mcp = Path.home() / ".kiro" / "settings" / "mcp.json"
    if mcp.exists():
        try:
            cfg = _json.loads(mcp.read_text())
            for srv in cfg.get("mcpServers", {}).values():
                k = (srv.get("env") or {}).get("BRAVE_API_KEY")
                if k:
                    return k
        except Exception:
            pass
    return None


def brave_search(query, count=6, timeout=20):
    """Deterministic Brave web search in Python. Returns [{title,url,description}].

    This guarantees the researcher has real web results regardless of whether the MCP
    attaches to the kiro-cli subprocess — the sourcing non-negotiable holds by construction.
    """
    key = _brave_key()
    if not key:
        return []
    url = f"{BRAVE_ENDPOINT}?{urllib.parse.urlencode({'q': query, 'count': count})}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "X-Subscription-Token": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    out = []
    for r in data.get("web", {}).get("results", []):
        out.append({"title": r.get("title", ""), "url": r.get("url", ""),
                    "description": r.get("description", "")})
    return out
# Tool names the researcher is allowed to use (configurable — adjust if the MCP exposes
# different names). The researcher reports NO_WEB_TOOL if none are reachable.
WEB_TOOLS = "brave_web_search,brave_search,web_search,fetch,mcp_fetch"

CHANNEL_CONTEXT = """CHANNEL: Leverage Mind — a faceless, premium educational channel.
Host persona: James Harrington (~60yo British, RP, calm, measured, lightly contrarian).
Audience: mid-career white-collar professionals (30-45, $90k+), time-poor, skeptical of
generic content. Pillars: AI for professional leverage (primary), learning/productivity/
personal OS, career capital & wealth frameworks. Every video needs an ORIGINAL framework or
insight + at least one concrete, sourced data point. (No other channel videos exist yet.)"""


def build_research_prompt(seed, video_type, search_results=None):
    from episode_format import format_block
    results_block = ""
    if search_results:
        lines = []
        for i, r in enumerate(search_results, 1):
            tag = "[REPUTABLE]" if r.get("reputable") else "[web]"
            lines.append(f"{tag} [{i}] {r['title']}\n    URL: {r['url']}\n    {r.get('description','')}")
        results_block = (
            "\n\nLIVE WEB SEARCH RESULTS (real, retrieved just now — ground your claims in THESE; "
            "you may cite their URLs directly. Do NOT invent URLs or studies not represented here. "
            "If a result is a secondary/popular source, treat it as a pointer to the underlying "
            "primary study and cite accordingly):\n\n" + "\n\n".join(lines))
    return f"""You are the RESEARCHER for an educational YouTube channel. Real web search results are
provided below. Produce sourced research material a scriptwriter can build a video from.

{CHANNEL_CONTEXT}

{format_block(video_type)}

SEED TOPIC: "{seed}"
{results_block}

SOURCE QUALITY GUIDANCE:
PREFER sources from reputable domains (marked [REPUTABLE] above): academic journals,
universities, business schools, management journals, reputable tech/AI publications.
Treat blogs/listicles/marketing pages (marked [web]) as weak; use them only for leads,
not as primary citations. TED talks and popular media = trend input ONLY, never a primary source.

YOUR TASK:
1. From the search results above (and your knowledge to interpret them), identify the most
   credible, SPECIFIC, and SURPRISING findings (peer-reviewed studies, named researchers, real
   statistics with dates). Prefer primary sources; treat popular articles as pointers to the
   underlying study.
2. Use at least THREE independent credible sources. For each claim you hand the writer, record
   the EXACT source (title, author or site, year, URL FROM THE RESULTS ABOVE). Do NOT invent or
   approximate statistics, and do NOT cite a URL that is not in the results above.
3. Identify the single most counterintuitive / share-worthy angle for this audience.
4. Suggest 3-5 emotional, curiosity-driven titles.

TARGET: Produce 6-10 well-sourced key_claims (minimum 4, more if the material supports it).
Do NOT pad with weak or invented claims to hit a number — quality over quantity, but do not
stop at the bare minimum if good sources exist.

SOURCING IS A LEGAL NON-NEGOTIABLE: every key_claim MUST map to a real URL from the results.
If the results are empty or unusable, reply with EXACTLY: NO_WEB_TOOL (do not fabricate).

Return ONLY JSON:
{{
  "seed": "{seed}",
  "angle": "<the most counterintuitive, audience-relevant framing>",
  "key_claims": [
    {{"claim": "<precise factual statement>", "source": {{"title": "...", "author_or_site": "...", "year": "...", "url": "..."}}}}
  ],
  "research_text": "<4-8 paragraphs of synthesised, source-grounded background the writer can use>",
  "sources": [{{"title": "...", "url": "...", "year": "..."}}],
  "suggested_titles": ["...", "..."]
}}
"""


def _extract_json(stdout):
    # strip ANSI (incl 8-bit color) + kiro '> ' prefixes, then find the JSON object
    clean = re.sub(r'\x1b\[[0-9;:?]*[ -/]*[@-~]', '', stdout)
    lines = []
    for ln in clean.splitlines():
        s = ln.lstrip()
        lines.append(s[2:] if s.startswith("> ") else s)
    text = "\n".join(lines)
    if re.search(r'^\s*NO_WEB_TOOL\s*$', text, re.MULTILINE) and '{' not in text:
        return {"error": "NO_WEB_TOOL"}, text
    # Prefer a fenced ```json block; else find the LAST top-level {...} that parses
    candidates = []
    for m in re.finditer(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL):
        candidates.append(m.group(1))
    candidates.append(text)
    for cand in candidates:
        # try every '{' as a start, longest-match first, last-occurring first
        starts = [i for i, c in enumerate(cand) if c == '{']
        for start in reversed(starts):
            depth, instr, esc = 0, False, False
            for i in range(start, len(cand)):
                ch = cand[i]
                if instr:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        instr = False
                    continue
                if ch == '"':
                    instr = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        blob = cand[start:i + 1]
                        try:
                            obj = json.loads(blob)
                            if isinstance(obj, dict) and ("angle" in obj or "key_claims" in obj):
                                return obj, text
                        except json.JSONDecodeError:
                            pass
                        break
    return None, text


def gather_research(seed, video_type="short"):
    """Deterministic web research up to (but excluding) LLM synthesis.

    Builds the query set, Brave-searches each query, tags reputable domains, sorts
    reputable-first, caps to MAX_RESULTS_FOR_PROMPT, and builds the prompt. Returns
    (results, prompt). No LLM/subprocess call — hermetic, so tests can exercise the real
    sort/cap/prompt/query logic without kiro-cli (D-018: research()'s synthesis step runs
    kiro-cli as a subprocess with no YT_TEST_MODE guard and would stall the suite).
    """
    queries = [
        seed,
        f"{seed} study findings statistics",
        f"{seed} peer-reviewed research OR randomized controlled trial",
        f"{seed} site:hbr.org OR site:sloanreview.mit.edu OR site:mckinsey.com",
        f"{seed} site:nature.com OR site:sciencedirect.com OR site:arxiv.org",
        f"{seed} business school OR university research",
    ]
    results, seen = [], set()
    for q in queries:
        for r in brave_search(q, count=8):
            if r["url"] and r["url"] not in seen:
                seen.add(r["url"])
                results.append(r)
    for r in results:
        r["reputable"] = _is_reputable(r["url"])
    results.sort(key=lambda r: (not r["reputable"],))
    results = results[:MAX_RESULTS_FOR_PROMPT]
    prompt = build_research_prompt(seed, video_type, search_results=results)
    return results, prompt


def research(seed, video_type="short", model="claude-sonnet-4.6", timeout=300,
             dry_run=False, transcript_path=None):
    """Deterministic web research: Python Brave-searches the seed, injects real results, then
    the LLM synthesizes a sourced brief. Returns (brief_dict_or_None, prompt, raw_output)."""
    if dry_run:
        # No external work (no search, no synthesis): placeholder prompt only.
        return None, build_research_prompt(seed, video_type, search_results=[]), "(dry-run)"
    # 1) Python-side web search + reputable sort/cap + prompt (hermetic; no LLM call).
    results, prompt = gather_research(seed, video_type)
    if not results:
        if transcript_path:
            Path(transcript_path).write_text(
                f"# Researcher\n\nNO web results (Brave key missing or search failed).\n")
        return {"error": "NO_WEB_TOOL"}, prompt, "(no search results)"
    # 2) LLM synthesis — tool-less call (safe), results already in the prompt.
    cmd = [KIRO, "chat", "--no-interactive", "--model", model, "--wrap", "never",
           "--trust-tools=", prompt]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    raw = r.stdout
    if transcript_path:
        Path(transcript_path).write_text(
            f"# Researcher — prompt + output\n\n## WEB SEARCH ({len(results)} results)\n\n" +
            "\n".join(f"- {x['title']} — {x['url']}" for x in results) +
            f"\n\n## PROMPT\n\n```\n{prompt}\n```\n\n"
            f"## RAW OUTPUT ({time.time()-t0:.0f}s, model {model})\n\n```\n{raw}\n```\n")
    data, _ = _extract_json(raw)
    return data, prompt, raw


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--format", dest="video_type", default="short")
    ap.add_argument("--model", default="claude-sonnet-4.6")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--output")
    ap.add_argument("--transcript")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    data, prompt, raw = research(args.seed, args.video_type, args.model, args.timeout,
                                 args.dry_run, args.transcript)
    if args.dry_run:
        print(f"  DRY RUN — researcher prompt {len(prompt)} chars, tools={WEB_TOOLS}")
        return 0
    if not data:
        print("  researcher: FAILED to parse JSON (see transcript)")
        return 1
    if data.get("error") == "NO_WEB_TOOL":
        print("  researcher: NO_WEB_TOOL — web tools not reachable; fix MCP before proceeding")
        return 2
    print(f"  research: angle={data.get('angle','')[:60]!r}  "
          f"{len(data.get('key_claims', []))} claims, {len(data.get('sources', []))} sources")
    if args.output:
        Path(args.output).write_text(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
