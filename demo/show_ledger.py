#!/usr/bin/env python3
"""demo/show_ledger.py — pretty-print the Landauer Reality Ledger (ledger/landauer_events.jsonl).

Every row is one receipt: who proposed what, under which policy, whether a human approved, the dollar
and joule estimates vs caps, the decision, and why. Real Stripe object ids and real nvidia-smi joules
are surfaced so a judge can verify them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from landauer import Ledger

_ANSI = {"green": "92", "red": "91", "yellow": "93", "cyan": "96", "dim": "2", "bold": "1"}


def _c(text: str, color: str) -> str:
    return f"\033[{_ANSI.get(color, '0')}m{text}\033[0m"


def _decision_color(d: str) -> str:
    return {"allowed": "green", "blocked": "red", "escalate": "yellow"}.get(d, "cyan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(ROOT / "ledger" / "landauer_events.jsonl"))
    args = ap.parse_args()

    rows = Ledger(args.ledger).read_all()
    if not rows:
        print(f"(empty ledger — run: python demo/run_landauer_demo.py)")
        return 0

    print(_c("\nLANDAUER REALITY LEDGER", "bold") + _c(f"   {args.ledger}", "dim"))
    header = f"{'#':<13}{'TIME':<9}{'ACTION':<22}{'HUMAN':<6}{'USD':<13}{'JOULES':<14}{'DECISION':<10}{'REASON':<30}"
    print(_c(header, "dim"))
    print(_c("─" * len(header), "dim"))

    for r in rows:
        t = str(r.get("timestamp", ""))[11:19] or "—"
        usd = "—" if r.get("usd_estimate") is None else f"${r['usd_estimate']:.2f}/${r['usd_cap']:.2f}"
        jou = "—" if r.get("joules_estimate") is None else f"{r['joules_estimate']:,.0f}/{r['joules_cap']:,.0f}"
        human = "yes" if r.get("human_approved") else "no"
        dec = r.get("decision", "")
        line = (f"{r.get('receipt_id',''):<13}{t:<9}{r.get('action',''):<22}{human:<6}"
                f"{usd:<13}{jou:<14}")
        print(line + _c(f"{dec.upper():<10}", _decision_color(dec)) + f"{r.get('reason',''):<30}")
        # surface real receipts under the row
        extras = []
        if r.get("stripe_object_id") and not str(r["stripe_object_id"]).startswith("pi_SIMULATED"):
            extras.append(_c(f"stripe:{r['stripe_object_id']}", "cyan"))
        tele = r.get("nvidia_telemetry") or {}
        if tele:
            src = "REAL nvidia-smi" if tele.get("source") == "nvidia-smi" else "MODELED"
            extras.append(_c(f"measured {float(tele.get('joules', 0)):,.0f} J @ "
                             f"{float(tele.get('avg_w', 0)):.1f} W [{src}]", "green"))
        if extras:
            print(" " * 13 + "└ " + "   ".join(extras))

    n = len(rows)
    allowed = sum(1 for r in rows if r["decision"] == "allowed")
    blocked = sum(1 for r in rows if r["decision"] == "blocked")
    esc = sum(1 for r in rows if r["decision"] == "escalate")
    print(_c("─" * len(header), "dim"))
    print(f"{n} receipts · {_c(str(allowed)+' allowed','green')} · "
          f"{_c(str(blocked)+' blocked','red')} · {_c(str(esc)+' escalate','yellow')}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
