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
KILO = "kilo"
KILO_MODEL = "kilo/deepseek/deepseek-v4-flash"
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

# System prompt enforcing strict JSON-only output from the model.
# Prepended as "SYSTEM:\n...\n\nUSER:\n..." so deepseek treats it as a system instruction.
RESEARCH_SYSTEM_PROMPT = """You are a JSON-only research API for a premium educational YouTube channel.

ABSOLUTE OUTPUT RULE: Your entire response MUST be a single valid JSON object and nothing else.
- No prose. No markdown. No bullet points. No preamble. No explanation. No summary.
- Do NOT write sentences like "Here is the research" or "I have identified...".
- Do NOT use ```json fences. Output the raw JSON object directly.
- The ONLY acceptable response format is: { "seed": ..., "angle": ..., ... }
- If you cannot produce valid sourced JSON, output exactly: NO_WEB_TOOL

Any response that is not a raw JSON object or the string NO_WEB_TOOL is a critical failure."""


def build_research_prompt(seed, video_type, search_results=None):
    from episode_format import format_block
    results_block = ""
    if search_results:
        lines = []
        for i, r in enumerate(search_results, 1):
            tag = "[REPUTABLE]" if r.get("reputable") else "[web]"
            lines.append(f"{tag} [{i}] {r['title']}\n    URL: {r['url']}\n    {r.get('description','')}")
        results_block = (
            "\n\nLIVE WEB SEARCH RESULTS (retrieved just now via Brave — ground every claim in "
            "THESE results only. Cite URLs exactly as they appear below. Do NOT invent URLs, "
            "statistics, or studies not in these results. If a result is a secondary/popular "
            "source, treat it as a pointer to the underlying primary study and cite accordingly):"
            "\n\n" + "\n\n".join(lines))

    user_block = f"""You are the RESEARCHER for an educational YouTube channel.
Real web search results are provided below. Produce high-quality sourced research material
that a scriptwriter can build a compelling, credible video from.

{CHANNEL_CONTEXT}

{format_block(video_type)}

SEED TOPIC: "{seed}"
{results_block}

SOURCE QUALITY RULES (non-negotiable):
- PREFER [REPUTABLE] sources: peer-reviewed journals, university research, HBR, MIT Sloan,
  McKinsey, Nature, Science, arXiv, PubMed, IEEE, ACM, .edu domains.
- Treat [web] sources as weak leads only — never cite as a primary source.
- TED talks and popular media = trend signal ONLY, never a primary citation.
- Each key_claim MUST cite a URL that appears verbatim in the results above.
- Do NOT invent, approximate, or extrapolate statistics. Use the exact figures from sources.
- Prefer SPECIFIC quantitative findings (percentages, study sizes, named researchers, years)
  over vague qualitative claims.

YOUR TASK:
1. Identify the most credible, specific, and SURPRISING findings from the search results.
   Extract named statistics, study authors, publication years, and exact figures.
2. Find the single most counterintuitive, share-worthy angle for a time-poor professional
   audience that is skeptical of generic AI productivity content.
3. Produce 6-10 well-sourced key_claims (minimum 4). Each claim must be a precise, factual
   statement with an exact source citation from the results above.
4. Write 4-8 paragraphs of synthesised background text the writer can draw from directly.
5. Suggest 3-5 emotionally compelling, curiosity-driven titles suited to the format.

SOURCING IS A LEGAL NON-NEGOTIABLE: every key_claim MUST map to a real URL from the results.
If the results are empty or unusable, output exactly: NO_WEB_TOOL

OUTPUT FORMAT — respond with this exact JSON structure and no other text:
{{
  "seed": "{seed}",
  "angle": "<single most counterintuitive, audience-relevant framing — one sentence>",
  "key_claims": [
    {{
      "claim": "<precise, quantitative factual statement>",
      "source": {{"title": "...", "author_or_site": "...", "year": "...", "url": "<exact URL from results>"}}
    }}
  ],
  "research_text": "<4-8 paragraphs of synthesised, source-grounded background>",
  "sources": [{{"title": "...", "url": "...", "year": "..."}}],
  "suggested_titles": ["...", "..."]
}}"""

    return f"SYSTEM:\n{RESEARCH_SYSTEM_PROMPT}\n\nUSER:\n{user_block}"


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


def call_kilo_synthesis(prompt, model=KILO_MODEL, timeout=300, verbose=False):
    """Run kilo subprocess for research synthesis and return raw stdout (NDJSON).

    Uses `kilo run --model <model> --format json` with prompt piped via stdin.
    kilo outputs NDJSON events on stdout. The caller uses _extract_json() to parse.
    """
    cmd = [KILO, "run", "--model", model, "--format", "json"]
    if verbose:
        print(f"  cmd: {KILO} run --model {model} --format json "
              f"[stdin: {len(prompt)} chars]", file=sys.stderr)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           input=prompt)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"kilo did not respond within {timeout}s (model {model}). "
            "Check `kilo models` and that your session is authenticated.")
    elapsed = time.time() - t0
    if verbose:
        print(f"  elapsed: {elapsed:.1f}s, exit: {r.returncode}", file=sys.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"kilo exited {r.returncode}: {r.stderr[:200]}")
    # Parse NDJSON: extract text from {"type":"text","part":{"text":"..."}} events
    parts = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "text":
                text = event.get("part", {}).get("text", "")
                if text:
                    parts.append(text)
        except json.JSONDecodeError:
            continue
    return "".join(parts).strip() if parts else r.stdout


# ARCHIVED: kiro-cli synthesis method, not called. Re-enable by switching research()
# to use the kiro-cli subprocess call below.
# cmd = [KIRO, "chat", "--no-interactive", "--model", model, "--wrap", "never",
#        "--trust-tools=", prompt]
# r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
#                    stdin=subprocess.DEVNULL)
# raw = r.stdout


def research(seed, video_type="short", model=KILO_MODEL, timeout=300,
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
    raw = call_kilo_synthesis(prompt, model=model, timeout=timeout)
    if transcript_path:
        Path(transcript_path).write_text(
            f"# Researcher — prompt + output\n\n## WEB SEARCH ({len(results)} results)\n\n" +
            "\n".join(f"- {x['title']} — {x['url']}" for x in results) +
            f"\n\n## PROMPT\n\n```\n{prompt}\n```\n\n"
            f"## RAW OUTPUT (model {model})\n\n```\n{raw}\n```\n")
    data, _ = _extract_json(raw)
    return data, prompt, raw


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--format", dest="video_type", default="short")
    ap.add_argument("--model", default=KILO_MODEL)
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
