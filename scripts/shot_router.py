#!/usr/bin/env python3
"""shot_router.py — Shot-type based model routing for James production flow.

Reads configs/james/model_routing.yaml, resolves model IDs, validates availability,
and returns the correct Higgsfield model + prompt template for each segment.

Usage (as library):
    from shot_router import ShotRouter
    router = ShotRouter()
    model_id, prompt, policy = router.resolve("talking_head_hero")

Usage (CLI validation):
    python3 scripts/shot_router.py validate                     # validate config + model availability
    python3 scripts/shot_router.py resolve talking_head_hero    # show resolved model for a shot_type
    python3 scripts/shot_router.py plan script.json             # show routing plan for all segments
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "configs" / "james" / "model_routing.yaml"


def _load_yaml(path):
    import yaml
    return yaml.safe_load(path.read_text())


def _get_available_models():
    """Query Higgsfield CLI for available video model IDs."""
    hf = ROOT / "node_modules" / "@higgsfield" / "cli" / "bin" / "higgsfield.js"
    try:
        r = subprocess.run(["node", str(hf), "model", "list", "--json"],
                           capture_output=True, text=True, timeout=30)
        data = json.loads(r.stdout)
        items = data if isinstance(data, list) else data.get("models", data.get("data", []))
        return {m["job_set_type"] for m in items if m.get("type") == "video"}
    except Exception:
        return set()


class ShotRouter:
    def __init__(self, config_path=None, skip_availability_check=False):
        self.config = _load_yaml(config_path or CONFIG_PATH)
        self.model_id_map = self.config.get("model_id_map", {})
        self.routes = self.config.get("shot_type_routes", {})
        self.templates = self.config.get("prompt_templates", {})
        self.narration_cfg = self.config.get("narration", {})
        self._available = None if skip_availability_check else _get_available_models()

    def _resolve_id(self, logical_name):
        """Map a logical model name to the actual Higgsfield job_set_type."""
        return self.model_id_map.get(logical_name, logical_name)

    def _check_available(self, model_id, logical_name):
        """Fail loudly if model is not available."""
        if self._available is not None and model_id not in self._available:
            raise RuntimeError(
                f"BLOCKED: model {logical_name!r} (resolved: {model_id!r}) "
                f"is not available in Higgsfield CLI. "
                f"Available: {sorted(self._available)}")

    def resolve(self, shot_type, allow_alternate=False):
        banned = set(self.config.get('banned_models', []))
        """Resolve shot_type → (model_id, prompt_template, policy_dict).

        Fails loudly if primary is unavailable and allow_alternate=False.
        """
        if shot_type not in self.routes:
            raise ValueError(
                f"Unknown shot_type: {shot_type!r}. "
                f"Available: {sorted(self.routes.keys())}")

        policy = self.routes[shot_type]
        primary_logical = policy.get('model', policy.get('primary', ''))
        primary_id = self._resolve_id(primary_logical)
        if primary_id in banned:
            raise RuntimeError(f'BLOCKED: model {primary_id!r} is banned per configs/james/model_routing.yaml')

        # Check availability
        try:
            self._check_available(primary_id, primary_logical)
            chosen_id = primary_id
            chosen_reason = f"primary: {primary_logical}"
        except RuntimeError:
            if not allow_alternate or not policy.get("alternates"):
                raise
            # Try alternates in order
            chosen_id = None
            for alt in policy["alternates"]:
                alt_id = self._resolve_id(alt)
                if self._available is None or alt_id in self._available:
                    chosen_id = alt_id
                    chosen_reason = f"alternate: {alt} (primary {primary_logical} unavailable)"
                    break
            if not chosen_id:
                raise RuntimeError(
                    f"BLOCKED: no available model for shot_type {shot_type!r}. "
                    f"Primary {primary_logical} and all alternates unavailable.")

        # Get prompt template
        template_key = policy.get("prompt_template", shot_type)
        prompt = self.templates.get(template_key, "")

        return chosen_id, prompt.strip(), {**policy, "resolved_model_id": chosen_id,
                                            "reason": chosen_reason}

    def plan_segment(self, segment, allow_alternate=False):
        """Plan routing for a single segment dict (must have shot_type)."""
        shot_type = segment.get("shot_type")
        if not shot_type:
            raise ValueError(
                f"Segment {segment.get('id', '?')!r} has no shot_type. "
                f"Every segment must specify shot_type for routed generation.")
        model_id, prompt, policy = self.resolve(shot_type, allow_alternate)
        return {
            "segment_id": segment.get("id"),
            "shot_type": shot_type,
            "resolved_model_id": model_id,
            "prompt_template": prompt[:80] + "..." if len(prompt) > 80 else prompt,
            "requires_audio": policy.get("requires_audio", False),
            "preserve_baked_audio": policy.get("preserve_baked_audio", False),
            "premium": policy.get("premium", False),
            "reason": policy["reason"],
        }

    def validate_config(self):
        """Validate all configured models are resolvable and available."""
        errors = []
        for shot_type, policy in self.routes.items():
            primary_id = self._resolve_id(policy["primary"])
            if self._available and primary_id not in self._available:
                errors.append(f"{shot_type}: primary {policy['primary']} → {primary_id} NOT AVAILABLE")
        return errors


def main():
    ap = argparse.ArgumentParser(description="Shot-type model router.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("validate", help="Validate config + model availability")
    p_res = sub.add_parser("resolve", help="Resolve one shot_type")
    p_res.add_argument("shot_type")
    p_plan = sub.add_parser("plan", help="Show routing plan for a script")
    p_plan.add_argument("script", help="Script JSON path")
    args = ap.parse_args()

    router = ShotRouter()

    if args.cmd == "validate":
        errors = router.validate_config()
        if errors:
            print("VALIDATION ERRORS:")
            for e in errors:
                print(f"  ✗ {e}")
            sys.exit(1)
        print(f"✓ All {len(router.routes)} shot_types validated against CLI model catalog.")

    elif args.cmd == "resolve":
        model_id, prompt, policy = router.resolve(args.shot_type, allow_alternate=True)
        print(f"shot_type:  {args.shot_type}")
        print(f"model_id:   {model_id}")
        print(f"reason:     {policy['reason']}")
        print(f"audio:      {policy.get('requires_audio')}")
        print(f"premium:    {policy.get('premium')}")
        print(f"prompt:     {prompt[:120]}...")

    elif args.cmd == "plan":
        script = json.load(open(args.script))
        segments = script.get("segments", [])
        # Add shot_type from james_segments config if not in script
        james_map = router.config.get("james_segments", {})
        total_premium = 0
        print(f"Routing plan for {script.get('project_id')}:")
        for seg in segments:
            sid = seg["id"]
            if not seg.get("shot_type") and sid in james_map:
                seg["shot_type"] = james_map[sid]["shot_type"]
            try:
                plan = router.plan_segment(seg, allow_alternate=True)
                icon = "★" if plan["premium"] else "·"
                print(f"  {icon} [{sid}] {plan['shot_type']:25s} → {plan['resolved_model_id']:20s} "
                      f"audio={'✓' if plan['requires_audio'] else '·'} ({plan['reason']})")
                if plan["premium"]:
                    total_premium += 1
            except (ValueError, RuntimeError) as e:
                print(f"  ✗ [{sid}] ERROR: {e}")
        print(f"\n  {len(segments)} segments, {total_premium} premium")

    else:
        ap.print_help()


if __name__ == "__main__":
    main()
