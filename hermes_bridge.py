"""
Hermes Bridge for Protos — execution layer for the Lead-to-Revenue Micro-Agency.

Protos (core) governs and plans. Hermes executes the redundant ops work (research, qualification,
outreach drafting). This bridge calls the local Hermes CLI CORRECTLY and fails LOUD: it never
claims success it did not achieve.

Two truths this file respects (both verified against the installed tooling):
  1. The Hermes CLI needs a real form: `hermes -z "<prompt>"` (one-shot, clean output) or
     `hermes chat -q "<prompt>" -s <skill>`. Passing a bare prompt as the subcommand is what made
     every previous call return an argparse "invalid choice" error.
  2. Stripe Link CLI is a SPEND/buy tool (the agent pays merchants under human approval), NOT an
     earn/get-paid tool. Client billing (the earn loop) is handled by stripe_earn.py via the Stripe
     API. This bridge does not pretend link-cli can create incoming revenue.

Default mode is SIMULATE (clearly labeled) so the demo never silently depends on inference auth.
Pass real=True to actually invoke Hermes.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

HERMES_DEFAULT = "/Users/qhantom/.local/bin/hermes"

# Hermes exits 0 even when the inference API errors (it prints the error to stdout), so returncode
# alone is not success. Detect these in the output and report honestly.
_ERR_MARKERS = ("API call failed", "requires available credits", "no final response",
                "[HERMES ERROR]", "temporarily unavailable", "HTTP 4", "HTTP 5",
                "capacity limits", "rate limit")
_TRANSIENT = ("temporarily unavailable", "capacity limits", "HTTP 503", "HTTP 429", "rate limit", "try again")


def _run_hermes(args: List[str], hermes_path: str = HERMES_DEFAULT, timeout: int = 120) -> Dict[str, Any]:
    """Invoke Hermes with an argv LIST (shell=False) so prompt content can never re-break parsing
    or inject shell commands. Returns a structured result; callers decide ok vs error."""
    try:
        proc = subprocess.run([hermes_path] + args, shell=False,
                              capture_output=True, text=True, timeout=timeout)
        return {
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "argv": [hermes_path] + args,
        }
    except FileNotFoundError:
        return {"returncode": 127, "ok": False, "stdout": "", "stderr": f"hermes not found at {hermes_path}", "argv": [hermes_path] + args}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "ok": False, "stdout": "", "stderr": f"timeout after {timeout}s", "argv": [hermes_path] + args}
    except Exception as e:
        return {"returncode": 1, "ok": False, "stdout": "", "stderr": str(e), "argv": [hermes_path] + args}


def hermes_available(hermes_path: str = HERMES_DEFAULT) -> Dict[str, Any]:
    """Cheap real check: `hermes --version`."""
    r = _run_hermes(["--version"], hermes_path, timeout=20)
    return {"available": r["ok"], "version": (r["stdout"] or r["stderr"]).strip()[:120]}


def fulfill_lead_ops_cycle(brief: str, skill: str = "revenue-ops-lead-to-revenue",
                           real: bool = False, hermes_path: str = HERMES_DEFAULT) -> Dict[str, Any]:
    """Run (or simulate) the redundant lead-ops work: research, qualify, draft outreach.
    Returns a structured result whose `status` is the single source of truth for the dashboard."""
    # Single-turn, no-tools prompt: loading --skills can otherwise trigger a multi-turn agentic run
    # (research with no web tools configured) that spins to timeout. This stays one fast generation
    # while still demonstrating the loaded skill's v2 heuristic (pain-point recency + trigger-led).
    prompt = (
        "You are running under the revenue-ops-lead-to-revenue skill, governed by Protos. "
        "In a SINGLE response, with NO tool calls and NO web research — invent one realistic example. "
        "Under 140 words, output exactly: (1) a 2-line prospect profile relevant to the brief, "
        "(2) a qualification score 0-100 with one-line reasoning (weight pain-point + budget-signal "
        "recency over static firmographics), (3) a 2-sentence personalized outreach opener that leads "
        "with the specific trigger event. No preamble, no generic templates.\n\n"
        f"BRIEF: {brief}"
    )

    if not real:
        return {
            "status": "dry_run",
            "skill_used": f"{skill} (local Hermes skill)",
            "prompt_used": prompt,
            "output": ("[DRY-RUN — Hermes not invoked] Sample qualified lead: 'Northgate Roofing', "
                       "trigger=hailstorm permit spike (last 14d), fit 9/10, budget signal high, timing now. "
                       "Outreach opener references the permit spike directly. Value: 1 booked-call-ready lead."),
            "note": "Default mode. Run the runner with --real-hermes to invoke Hermes for real.",
        }

    avail = hermes_available(hermes_path)
    if not avail["available"]:
        return {"status": "error", "skill_used": skill, "prompt_used": prompt,
                "error": f"Hermes unavailable: {avail['version']}",
                "note": "Real mode requested but Hermes/inference is not ready. NOT claiming success."}

    out, ok, attempts = "", False, 0
    for attempt in range(2):  # retry once on transient capacity/rate errors (free tier is flaky)
        attempts = attempt + 1
        r = _run_hermes(["-z", prompt, "--skills", skill], hermes_path, timeout=180)
        out = (r["stdout"] or "").strip()
        is_err = (not r["ok"]) or (not out) or any(m in out for m in _ERR_MARKERS)
        if not is_err:
            ok = True
            break
        if not any(t in out for t in _TRANSIENT):
            break  # permanent error (e.g. credits) — don't retry
    return {
        "status": "ok" if ok else "error",
        "skill_used": f"{skill} (local Hermes skill)",
        "prompt_used": prompt,
        "output": out if ok else "",
        "error": "" if ok else (out or "no output")[:1500],
        "attempts": attempts,
        "note": "Real Hermes invocation." if ok
                else "Real invocation FAILED (surfaced honestly, not faked) — often a free-tier capacity 503; add Nous credits or retry.",
    }


def demo_link_cli_spend(amount_usd: float, merchant: str, real: bool = False,
                        link_cli: str = "link-cli") -> Dict[str, Any]:
    """The SPEND side: the agent buys a tool/service under human approval via Stripe Link CLI (test mode).
    This is link-cli's correct use. Earning (client billing) lives in stripe_earn.py, not here."""
    if not real:
        return {
            "status": "dry_run",
            "tool": "@stripe/link-cli (test mode)",
            "flow": [f"agent: spend-request create --merchant '{merchant}' --amount {int(amount_usd*100)} --request-approval",
                     "human: approves in the Link app on phone (agent CANNOT self-approve)",
                     "over-limit requests are DENIED even after approval (bounded autonomy hard stop)"],
            "note": "Default simulated. Run link-cli onboard/demo in --test for the real on-camera flow.",
        }
    try:
        proc = subprocess.run([link_cli, "auth", "status"], shell=False, capture_output=True, text=True, timeout=30)
        return {"status": "ok" if proc.returncode == 0 else "error",
                "tool": "@stripe/link-cli", "output": (proc.stdout or proc.stderr)[:800],
                "note": "link-cli reachable; drive spend-request create/retrieve for the live spend demo."}
    except Exception as e:
        return {"status": "error", "tool": "@stripe/link-cli", "error": str(e),
                "note": "link-cli not on PATH. Alias it to the installed @stripe/link-cli dist, then retry."}
