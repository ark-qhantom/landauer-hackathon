"""landauer.adapters.hermes — the Hermes 'action proposer'.

Hermes is the agent runtime: it proposes the action to attempt. We call it in ONE shot with NO skill
loading (skill-loading triggers a multi-turn agentic loop that spins for minutes) and ask for STRICT
JSON, so the proposal is fast and parseable. If inference errors or returns unparseable text, we fall
back to a deterministic, clearly-labeled proposal — we never report a Hermes success we didn't get.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from hermes_bridge import HERMES_DEFAULT, _ERR_MARKERS, _run_hermes, hermes_available  # noqa: E402

_PROMPT = (
    "You are a Hermes agent proposing ONE next action for an autonomous revenue/compute workflow. "
    "Respond with STRICT JSON ONLY — no prose, no markdown fences — with exactly these keys: "
    '{{"action": "<one of: summarize_docs, call_api_model, run_local_model, large_gpu_job, public_post>", '
    '"usd_estimate": <number>, "joules_estimate": <number>, "runtime_seconds": <number>, '
    '"rationale": "<one short sentence>"}}. '
    "Context: {context}"
)


def _extract_json(text: str):
    text = (text or "").strip()
    try:                                   # the strict-JSON case first
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)   # else: scan for an object in surrounding prose
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def propose_action(context: str, *, hermes_path: str = HERMES_DEFAULT, real: bool = True,
                   timeout: int = 45) -> dict:
    """Ask Hermes for the next action as JSON. Returns a dict with at least `action` and a `source`
    field ('hermes' = real proposal, 'fallback' = deterministic stand-in)."""
    fallback = {"action": "call_api_model", "usd_estimate": 0.84, "joules_estimate": 0.0,
                "runtime_seconds": 3.0, "rationale": "deterministic fallback proposal",
                "source": "fallback"}
    if not real:
        return dict(fallback)

    avail = hermes_available(hermes_path)
    if not avail.get("available"):
        return {**fallback, "note": f"hermes unavailable: {avail.get('version', '')[:80]}"}

    # NO --skills: single fast generation, no agentic loop.
    r = _run_hermes(["-z", _PROMPT.format(context=context)], hermes_path, timeout=timeout)
    out = (r.get("stdout") or "").strip()
    # Parse first: a valid strict-JSON proposal is accepted even if its prose happens to mention e.g. "HTTP 5xx".
    parsed = _extract_json(out)
    if parsed and "action" in parsed:
        parsed["source"] = "hermes"
        parsed["raw"] = out[:400]
        return parsed
    # No usable proposal. Hermes exits 0 even when inference errors (prints the error to stdout) — classify the
    # failure honestly so an error/timeout is never confused with merely-unparseable output (never stamped real).
    if (not r.get("ok")) or (not out) or any(m in out for m in _ERR_MARKERS):
        first = (out.splitlines()[0] if out else (r.get("stderr") or "no output")).strip()
        return {**fallback, "note": f"hermes error/timeout: {first[:120]}", "raw": out[:400]}
    return {**fallback, "note": "unparseable hermes output", "raw": out[:400]}
