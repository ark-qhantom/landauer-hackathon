"""
stripe_earn.py — the REAL earn loop for the Protos Lead-to-Revenue Micro-Agency.

This is the money proof. It uses the Stripe API directly (the correct EARN primitive — Stripe Link
CLI is spend-only and cannot create incoming billing) to, in TEST MODE:

    products.create -> prices.create -> payment_links.create
    -> simulate a client paying (PaymentIntent with the test card pm_card_visa, confirmed)
    -> read the charge + balance transaction (net cents)

Every real object id (prod_/price_/plink_/pi_/ch_/txn_) is captured so a judge can paste it into
their own Stripe test dashboard. No live key is ever used.

KEY-OPTIONAL: with a Stripe sk_test_ key (env STRIPE_API_KEY, or in ~/.hermes/.env, or ./.env) and
the `stripe` package installed, this runs for real. Without them it returns the SAME shape clearly
labeled status="simulated" so the demo never breaks — but the dashboard must show that label.

Provision (Dylan, ~2 min):  pip install stripe ; export STRIPE_API_KEY=sk_test_...
Run standalone:             python3 stripe_earn.py
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


def _load_test_key() -> Optional[str]:
    key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    if key:
        return key.strip()
    names = ("STRIPE_API_KEY", "STRIPE_SECRET_KEY")
    for envfile in [Path.home() / ".hermes" / ".env", Path(__file__).parent / ".env"]:
        try:
            for raw in envfile.read_text().splitlines():
                line = raw.strip()
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                name, val = line.split("=", 1)
                if name.strip() not in names:
                    continue
                val = val.strip()
                if val and val[0] not in "\"'" and " #" in val:  # strip inline comment on unquoted value
                    val = val.split(" #", 1)[0].strip()
                return val.strip().strip('"').strip("'")
        except Exception:
            continue
    return None


def _simulated(offer_name: str, price_usd: float, reason: str) -> Dict[str, Any]:
    cents = int(round(price_usd * 100))
    # Realistic SHAPE, explicitly fake ids and status. The dashboard must render the 'simulated' label.
    return {
        "status": "simulated",
        "reason": reason,
        "mode": "test",
        "currency": "usd",
        "offer_name": offer_name,
        "price_usd": price_usd,
        "ids": {
            "product": "prod_SIMULATED",
            "price": "price_SIMULATED",
            "payment_link": "plink_SIMULATED",
            "payment_intent": "pi_SIMULATED",
            "charge": "ch_SIMULATED",
            "balance_txn": "txn_SIMULATED",
        },
        "payment_link_url": "https://buy.stripe.com/test_SIMULATED",
        "amount_captured_cents": cents,
        "net_cents": int(round(cents * 0.971)) - 30,   # rough Stripe 2.9% + 30c, for display realism
        "note": "SIMULATED — provide a Stripe sk_test_ key + `pip install stripe` to produce real, verifiable ids.",
    }


def run_earn_loop(offer_name: str, price_usd: float,
                  out_path: Optional[Path] = None, allow_real: bool = False) -> Dict[str, Any]:
    """Create real test-mode billing and a simulated client payment. Falls back to labeled simulation.

    Real mode is OFF by default and only engages when allow_real=True AND a test key is present — it
    never goes real on silent key presence, and never touches a live key (that refusal is a guardrail).
    """
    key = _load_test_key()
    if not allow_real:
        result = _simulated(offer_name, price_usd, "real mode off (pass --real-stripe to enable)")
    elif not key:
        result = _simulated(offer_name, price_usd, "no Stripe test key found (set STRIPE_API_KEY)")
    elif "_live_" in key:
        result = _simulated(offer_name, price_usd, "refusing to use a LIVE key — test keys only")
    elif not (key.startswith("sk_test_") or key.startswith("rk_test_")):
        result = _simulated(offer_name, price_usd, "key is not a recognized test key (sk_test_ / rk_test_)")
    else:
        try:
            import stripe  # type: ignore
        except ImportError:
            result = _simulated(offer_name, price_usd, "stripe package not installed (pip install stripe)")
        else:
            try:
                stripe.api_key = key
                cents = int(round(price_usd * 100))
                product = stripe.Product.create(
                    name=offer_name,
                    description="Per-qualified-lead billing for the Protos Lead-to-Revenue Micro-Agency (test mode).",
                )
                price = stripe.Price.create(unit_amount=cents, currency="usd", product=product.id)
                link = stripe.PaymentLink.create(line_items=[{"price": price.id, "quantity": 1}])
                # Simulate the client paying, in test mode, with Stripe's standard test card.
                intent = stripe.PaymentIntent.create(
                    amount=cents, currency="usd",
                    payment_method="pm_card_visa", confirm=True,
                    description=f"Test client payment for {offer_name}",
                    automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                    expand=["latest_charge"],
                )
                charge = intent.latest_charge  # expanded object (or None)
                charge_id = charge.id if charge else ""
                # The balance transaction (net-after-fees) attaches a beat after capture. Best-effort:
                # re-fetch the charge with it expanded; if not ready, net stays null and we report captured.
                txn, txn_id = None, ""
                if charge_id:
                    try:
                        fresh = stripe.Charge.retrieve(charge_id, expand=["balance_transaction"])
                        txn = fresh.balance_transaction
                        txn_id = txn.id if txn else ""
                    except Exception:
                        pass
                result = {
                    "status": "real",
                    "mode": "test",
                    "currency": "usd",
                    "offer_name": offer_name,
                    "price_usd": price_usd,
                    "ids": {
                        "product": product.id,
                        "price": price.id,
                        "payment_link": link.id,
                        "payment_intent": intent.id,
                        "charge": charge_id or "",
                        "balance_txn": txn_id or "",
                    },
                    "payment_link_url": link.url,
                    "amount_captured_cents": (charge.amount_captured if charge else cents),
                    "net_cents": (txn.net if txn else None),
                    "livemode": bool(getattr(intent, "livemode", False)),
                    "note": "REAL test-mode Stripe objects. Paste any id into your Stripe test dashboard to verify.",
                }
            except Exception as e:
                result = _simulated(offer_name, price_usd, f"Stripe API error: {e}")

    if out_path is not None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    r = run_earn_loop("LeadForge Micro-Agency", 49.0, allow_real=True)
    print(json.dumps(r, indent=2))
    print(f"\nstatus={r['status']}  net_cents={r.get('net_cents')}  link={r.get('payment_link_url')}")
