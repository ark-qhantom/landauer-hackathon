"""landauer.adapters.stripe_budget — Stripe-backed treasury adapter (test mode).

Holds the running USD budget and creates a REAL Stripe test-mode object when an ALLOWED action actually
spends. A BLOCKED spend never reaches Stripe — Landauer refuses before execution — so a ledger receipt
carries a real stripe_object_id exactly for the spends that really happened. Reuses the validated
key-loading from stripe_earn.py and the same PaymentIntent flow; no live key is ever used.
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from stripe_earn import _load_test_key  # noqa: E402


class StripeBudgetAdapter:
    def __init__(self, budget_usd: float, allow_real: bool = True):
        self.budget_usd = float(budget_usd)
        self.remaining = float(budget_usd)
        self.allow_real = allow_real
        self._key = _load_test_key()

    @property
    def mode(self) -> str:
        ok = self.allow_real and bool(self._key) and self._key.startswith(("sk_test_", "rk_test_"))
        return "test" if ok else "simulated"

    def status(self) -> dict:
        return {"mode": self.mode, "budget_usd": round(self.budget_usd, 2),
                "remaining": round(self.remaining, 2)}

    def can_afford(self, amount_usd: float) -> bool:
        return amount_usd <= self.remaining + 1e-9

    def charge(self, amount_usd: float, description: str) -> dict:
        """Charge an ALLOWED spend. Refuses (no debit, no Stripe call) if it would exceed the running
        treasury budget. Otherwise a real Stripe test-mode PaymentIntent when a test key is present and the
        amount clears the $0.50 minimum, else an honestly-labeled simulated id. Returns
        {stripe_object_id, real, charge_id, remaining, note}."""
        cents = int(round(amount_usd * 100))
        sim_id = f"pi_SIMULATED_{cents}"

        def _debit():
            self.remaining = round(self.remaining - amount_usd, 2)

        # Hard treasury guard: a cumulative budget that is actually enforced (no debit, no Stripe call).
        if not self.can_afford(amount_usd):
            return {"stripe_object_id": "", "real": False, "charge_id": "",
                    "remaining": round(self.remaining, 2),
                    "note": f"over budget: ${amount_usd:.2f} > ${self.remaining:.2f} remaining — not charged"}
        if self.mode != "test":
            _debit()
            note = ("live key refused — test keys only" if (self._key and "_live_" in self._key)
                    else "simulated (no Stripe test key)")
            return {"stripe_object_id": sim_id, "real": False, "charge_id": "",
                    "remaining": self.remaining, "note": note}
        if cents < 50:
            _debit()
            return {"stripe_object_id": sim_id, "real": False, "charge_id": "",
                    "remaining": self.remaining, "note": "below Stripe $0.50 minimum — simulated id"}
        obj_id = ""
        try:
            import stripe
            stripe.api_key = self._key
            intent = stripe.PaymentIntent.create(
                amount=cents, currency="usd",
                payment_method="pm_card_visa", confirm=True,
                description=description,
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                expand=["latest_charge"],
            )
            obj_id = intent.id   # captured BEFORE post-processing so a real spend is never relabeled fake
            charge = intent.latest_charge
            _debit()
            return {"stripe_object_id": obj_id, "real": True,
                    "charge_id": (charge.id if charge else ""),
                    "remaining": self.remaining, "note": "REAL Stripe test-mode PaymentIntent"}
        except Exception as e:
            if obj_id:   # the PaymentIntent really was created; only post-processing failed — keep the REAL id + debit
                _debit()
                return {"stripe_object_id": obj_id, "real": True, "charge_id": "",
                        "remaining": self.remaining,
                        "note": f"real PaymentIntent created; post-processing failed ({type(e).__name__})"}
            # create() itself failed — no money moved, so do NOT debit the budget
            return {"stripe_object_id": sim_id, "real": False, "charge_id": "",
                    "remaining": round(self.remaining, 2), "note": f"stripe error, NOT charged ({type(e).__name__})"}
