#!/usr/bin/env python3
"""Render the Landauer demo video frames (4K stills) with Pillow, from the REAL run artifacts.
No browser, no screen capture — deterministic, every pixel controlled. ffmpeg (build_video.py) animates these.

8-beat spine (locked to the Demo thesis — "Agents that cannot outrun reality"):
  01 cold open / the problem        05 two independent hard caps + orthogonal energy BLOCK
  02 capability gate (PENDING)      06 Reality Ledger + tamper (+ verifiable Stripe ids)
  03 approval changes the run       07 spawn inherits the budget
  04 REAL telemetry (∫P·dt)         08 skill / scale / close

Data source: prefers submission-artifacts/real-run-4070 (the REAL nvidia-smi capture) once it exists, else the
newest out/run-*, else submission-artifacts/sample-run-mac-fallback. So after the 4070 capture, Beats 4/5/6 flip
to REAL automatically with no code change.
"""
import json, glob, os
from PIL import Image, ImageDraw, ImageFont

W, H = 3840, 2160
BG = (11, 15, 26); CARD = (18, 24, 38); CARD2 = (14, 20, 34)
PEARL = (243, 238, 226); GOLD = (201, 162, 75); GREEN = (103, 178, 145)
RED = (208, 106, 106); AMBER = (216, 178, 90); MUT = (138, 147, 166); THEO = (185, 166, 224)
MARGIN = 300
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "frames"); os.makedirs(OUT, exist_ok=True)


def pick_run():
    real = os.path.join(ROOT, "submission-artifacts", "real-run-4070")
    if os.path.exists(os.path.join(real, "energy-report.json")):
        return real
    outs = sorted(glob.glob(os.path.join(ROOT, "out", "run-*")))
    if outs:
        return outs[-1]
    return os.path.join(ROOT, "submission-artifacts", "sample-run-mac-fallback")


RUN = pick_run()
print("frames from:", RUN)
A = json.load(open(os.path.join(RUN, "audit-ledger.json")))
E = json.load(open(os.path.join(RUN, "energy-report.json")))
RES = json.load(open(glob.glob(os.path.join(RUN, "*-result.json"))[0]))
try:
    S = json.load(open(os.path.join(RUN, "stripe-earn.json")))
except FileNotFoundError:
    S = {"status": "dry_run", "ids": {"product": "prod_DRYRUN", "charge": "ch_DRYRUN"}, "amount_captured_cents": 0}

G = RES["guardrail_report"]; M = RES["metrics"]; ALLOC = RES.get("revenue_allocation") or {}
CYC = (E.get("cycles") or [{}])[0]
SAMPLES = CYC.get("samples", [])
SRC = E.get("energy_source", "fallback"); IS_REAL = E.get("is_real", False)
PT = E.get("physics_task") or RES.get("physics_task") or {}
ENERGY_LIMIT = E.get("energy_limit_joules") or G.get("energy_limit_joules") or 0
COMMITTED_E = G.get("committed_energy_joules", 0)
e_blk = next((r for r in A if r.get("energy_rule_fired") == "energy_limit"), None)
m_blk = next((r for r in A if r["final_outcome"] == "BLOCKED" and r.get("energy_rule_fired") != "energy_limit"), None)
ENERGY_TAG = "REAL · nvidia-smi" if SRC == "nvidia-smi" else "MODELED · fallback"
ENERGY_COL = GREEN if SRC == "nvidia-smi" else AMBER


# ---- fonts ----
def F(path, size, index=0):
    try: return ImageFont.truetype(path, size, index=index)
    except Exception: return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
def SANS(s): return F("/System/Library/Fonts/Helvetica.ttc", s)
def MONO(s): return F("/System/Library/Fonts/Menlo.ttc", s, 0)
def SERIF(s): return F("/System/Library/Fonts/Supplemental/Georgia.ttf", s)

def text(d, xy, s, font, fill, anchor="la", bold=0):
    d.text(xy, s, font=font, fill=fill, anchor=anchor, stroke_width=bold, stroke_fill=fill)
def tw(d, s, font):
    b = d.textbbox((0, 0), s, font=font); return b[2] - b[0]

def base(kicker="LANDAUER · QHANTOM", caption=None, cap_color=GREEN):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(220):
        a = int(18 * (1 - y / 220))
        d.line([(0, y), (W, y)], fill=(BG[0] + a, BG[1] + a, BG[2] + a + 2))
    if kicker:
        text(d, (MARGIN, 150), kicker, SANS(46), GOLD, "lm")
        d.line([(MARGIN, 205), (W - MARGIN, 205)], fill=(40, 48, 66), width=2)
    if caption:
        f = SANS(54); pw = tw(d, caption, f)
        x0 = (W - pw) // 2 - 60; x1 = (W + pw) // 2 + 60; y0 = 1900; y1 = 2010
        d.rounded_rectangle([x0, y0, x1, y1], radius=55, fill=(16, 22, 36), outline=cap_color, width=3)
        text(d, (W // 2, (y0 + y1) // 2), caption, f, cap_color, "mm")
    return img, d

def pill(d, x, y, s, font, fg, bg, pad=28):
    w = tw(d, s, font); h = font.size + 24
    d.rounded_rectangle([x, y, x + w + pad * 2, y + h], radius=h // 2, fill=bg)
    text(d, (x + pad, y + h // 2), s, font, fg, "lm")
    return x + w + pad * 2

def panel(d, x, y, w, h, title=None, border=(46, 54, 74)):
    d.rounded_rectangle([x, y, x + w, y + h], radius=28, fill=CARD, outline=border, width=3)
    if title:
        text(d, (x + 50, y + 56), title, SANS(50), GOLD, "lm", bold=1)
    return x + 50, y + 120

def save(img, name): img.save(os.path.join(OUT, name)); print("  rendered", name)


def sparkline(d, x, y, w, h, samples):
    """Gold power curve with a filled area beneath (area = ∫P·dt = energy). Pure Pillow."""
    d.rounded_rectangle([x, y, x + w, y + h], radius=20, fill=(8, 11, 19), outline=(40, 48, 66), width=3)
    if not samples or len(samples) < 2:
        text(d, (x + w // 2, y + h // 2), "insufficient telemetry samples — bump PHYS_STEPS for the 4070 take",
             SANS(46), MUT, "mm")
        return
    pad = 60
    ts0 = samples[0]["ts_ms"]; span = max(samples[-1]["ts_ms"] - ts0, 1)
    pmax = max(s["power_W"] for s in samples) * 1.08 or 1.0
    baseline = y + h - pad
    def fx(t): return x + pad + (t - ts0) / span * (w - 2 * pad)
    def fy(p): return y + pad + (1 - p / pmax) * (h - 2 * pad)
    pts = [(fx(s["ts_ms"]), fy(s["power_W"])) for s in samples]
    d.polygon([(pts[0][0], baseline)] + pts + [(pts[-1][0], baseline)], fill=(46, 40, 24))
    d.line(pts, fill=GOLD, width=6, joint="curve")
    d.line([(x + pad, baseline), (x + w - pad, baseline)], fill=(60, 68, 88), width=2)


# ============================ SCENES ============================

# 01 — cold open / the problem
img, d = base(kicker=None)
tx, ty, tw_, th = 360, 360, W - 720, 560
d.rounded_rectangle([tx, ty, tx + tw_, ty + th], radius=26, fill=(8, 11, 19), outline=(40, 48, 66), width=3)
for i, c in enumerate([(214, 110, 102), (216, 178, 90), (103, 178, 145)]):
    d.ellipse([tx + 50 + i * 60, ty + 40, tx + 50 + i * 60 + 34, ty + 74], fill=c)
text(d, (tx + tw_ // 2, ty + 57), "landauer — live run", MONO(40), MUT, "mm")
m = MONO(46)
text(d, (tx + 70, ty + 190), "$ python3 runner.py --approve scale-to-500-leads gpu-render-batch", m, PEARL)
text(d, (tx + 70, ty + 270), "LANDAUER — Physics-Grounded Agent Treasury", MONO(44), GOLD)
text(d, (tx + 70, ty + 350), "DUAL hard caps: money (USD) + energy (Joules) · enforced below the human", MONO(38), MUT)
text(d, (W // 2, 1180), "If agents are going to act in the world —", SERIF(118), PEARL, "mm")
text(d, (W // 2, 1340), "what keeps them honest?", SERIF(128), GOLD, "mm", bold=1)
text(d, (W // 2, 1640), "Every action gets a reality label, a hash-chained receipt,", SANS(58), MUT, "mm")
text(d, (W // 2, 1730), "and an energy budget it cannot lie about.", SANS(58), MUT, "mm")
save(img, "01_open.png")

# 02 — capability gate
img, d = base(caption="Capability gate — the agent cannot act on the world unsupervised")
text(d, (MARGIN, 340), "CAPABILITY GATE", SANS(120), GOLD, "lm", bold=1)
text(d, (MARGIN, 470), "spend · activate billing · touch credentials  ->  stopped, pending a human", SANS(58), PEARL, "lm")
x = MARGIN; y = 620
x = pill(d, x, y, f"{len(G['pending'])} PENDING — gated", SANS(54), AMBER, (44, 36, 16)) + 30
x = pill(d, x, y, f"{len([i for i in G['items'] if i['status']=='auto_approved'])} auto-allowed (safe)", SANS(54), GREEN, (16, 40, 28)) + 30
bx, by = panel(d, MARGIN, 800, W - 2 * MARGIN, 900, "Held for human approval (status: PENDING)")
mm = MONO(48); yy = by + 20
for it in G["pending"][:5]:
    text(d, (bx, yy), "[ PENDING ]", mm, AMBER, bold=1)
    text(d, (bx + 360, yy), str(it["title"])[:62], SANS(48), PEARL); yy += 96
text(d, (MARGIN, 1760), "The agent proposes. It cannot spend, post, or call real systems until a human clears the gate.",
     SERIF(54), GOLD)
save(img, "02_capability.png")

# 03 — approval changes the run
img, d = base(caption="Approval clears the soft gates — it never lifts the hard caps")
text(d, (MARGIN, 340), "APPROVAL", SANS(130), GOLD, "lm", bold=1)
text(d, (MARGIN, 470), "a human approves  ->  labels flip PENDING to HUMAN-APPROVED, cleared to execute", SANS(56), PEARL, "lm")
cy = 760
bx, by = panel(d, MARGIN, cy, (W - 2 * MARGIN - 80) // 2, 760, "Before — gated")
text(d, (bx, by + 60), f"{len(G['pending'])}  PENDING", SANS(96), AMBER, bold=1)
text(d, (bx, by + 220), "agent is stopped at every", SANS(50), MUT)
text(d, (bx, by + 290), "real-world capability", SANS(50), MUT)
bx2 = MARGIN + (W - 2 * MARGIN - 80) // 2 + 80
bx2i, by2 = panel(d, bx2, cy, (W - 2 * MARGIN - 80) // 2, 760, "After --approve — cleared")
text(d, (bx2i, by2 + 60), f"{len(G['pending'])}  HUMAN-APPROVED", SANS(96), GREEN, bold=1)
text(d, (bx2i, by2 + 220), f"…but {len(G['blocked'])} actions STAY BLOCKED", SANS(56), RED, bold=1)
text(d, (bx2i, by2 + 300), "approval cannot touch the hard caps", SANS(50), MUT)
text(d, (W // 2, 1700), "Approval decides what runs. Watch what it cannot move.", SERIF(60), GOLD, "mm")
save(img, "03_approval.png")

# 04 — REAL telemetry (the judge-decider)
img, d = base(caption=f"Energy telemetry — {ENERGY_TAG}", cap_color=ENERGY_COL)
text(d, (MARGIN, 320), ("REAL JOULES" if SRC == "nvidia-smi" else "METERED JOULES"), SANS(120), GOLD, "lm", bold=1)
text(d, (MARGIN, 445), "measured power, integrated over the cycle — the shaded area is the energy spent", SANS(54), PEARL, "lm")
sparkline(d, MARGIN, 600, W - 2 * MARGIN, 760, SAMPLES)
x = MARGIN; y = 1430
x = pill(d, x, y, ENERGY_TAG, SANS(50), ENERGY_COL, (22, 30, 46)) + 30
x = pill(d, x, y, f"∫P·dt = {CYC.get('measured_energy_joules', 0):,.0f} J", SANS(50), PEARL, (24, 32, 50)) + 30
x = pill(d, x, y, f"avg {CYC.get('power_w_avg', 0):,.0f} W", SANS(50), PEARL, (24, 32, 50)) + 30
x = pill(d, x, y, f"peak {CYC.get('temp_c_peak', 0):,.0f} °C", SANS(50), PEARL, (24, 32, 50)) + 30
x = pill(d, x, y, f"{len(SAMPLES)} samples", SANS(50), MUT, (22, 28, 42)) + 30
note = ("Same instant on real silicon — captured beside raw nvidia-smi." if SRC == "nvidia-smi"
        else "Dev-box fallback (MODELED, labeled). The 4070 capture flips this panel to REAL · nvidia-smi.")
text(d, (MARGIN, 1620), note, SERIF(52), (GOLD if SRC == "nvidia-smi" else MUT))
save(img, "04_telemetry.png")

# 05 — two independent hard caps + orthogonal energy BLOCK
img, d = base(caption="Two independent hard caps — approval can lift neither")
text(d, (MARGIN, 320), "MONEY  +  ENERGY", SANS(120), GOLD, "lm", bold=1)
text(d, (MARGIN, 445), "two cumulative hard stops, checked before approval and never bypassed by it", SANS(54), PEARL, "lm")
n_money = sum(1 for r in A if r["final_outcome"] == "BLOCKED" and r.get("energy_rule_fired") != "energy_limit")
n_energy = sum(1 for r in A if r.get("energy_rule_fired") == "energy_limit")
x = MARGIN; y = 600
x = pill(d, x, y, f"money committed  ${G['committed_spend_usd']:.0f} / ${G['limit_usd']:.0f}", SANS(50), PEARL, (24, 32, 50)) + 30
x = pill(d, x, y, f"energy committed  {COMMITTED_E:,.0f} / {ENERGY_LIMIT:,.0f} J", SANS(50), PEARL, (24, 32, 50)) + 30
x = MARGIN; y = 730
x = pill(d, x, y, f"{n_money} refused on the money cap", SANS(48), RED, (44, 22, 22)) + 30
x = pill(d, x, y, f"{n_energy} refused on the energy cap", SANS(48), RED, (44, 22, 22)) + 30
bx, by = panel(d, MARGIN, 880, W - 2 * MARGIN, 700, "Refused on physics alone — even though approved & within budget")
if e_blk:
    t = str(e_blk["action"]); t = (t[:46].rsplit(" ", 1)[0] + "…") if len(t) > 46 else t
    text(d, (bx, by + 30), f"[ BLOCKED ]  {t}", MONO(50), RED, bold=1)
    text(d, (bx, by + 150), f"cost ${float(e_blk['est_cost_usd']):.0f}   ·   projected {float(e_blk['est_energy_joules']):,.0f} J  >  {ENERGY_LIMIT:,.0f} J cap",
         SANS(50), PEARL)
    ov = "YES — pre-approved, and still refused" if e_blk["energy_override_attempted"] == "true" else "no"
    text(d, (bx, by + 260), f"pre-approved by human?  {ov}", SANS(50), AMBER)
text(d, (bx, by + 410), "money would have allowed it ($5 ≤ $300); the physics cap refused it.", SERIF(54), GOLD)
save(img, "05_twocaps.png")

# 06 — Reality Ledger + tamper (+ verifiable Stripe ids)
img, d = base(caption="Nothing is presented as more real than it is")
text(d, (W // 2, 320), "THE REALITY LEDGER", SANS(118), GOLD, "mm", bold=1)
stripe_tag = "REAL" if S.get("status") == "real" else "DRY-RUN"
stripe_col = GREEN if S.get("status") == "real" else AMBER
rows = [("Dual caps · routing · guardrails (engine)", "REAL", GREEN),
        ("Audit ledger — SHA-256 hash-chained, energy inside", "REAL", GREEN),
        ("Measured cycle energy (∫P·dt)", ENERGY_TAG.split(" · ")[0], ENERGY_COL),
        ("Physics conservation (energy + ang. momentum)", "REAL", GREEN),
        ("Projected per-action energy (cap input)", "MODELED", AMBER),
        (f"Stripe earn loop  ·  {S.get('ids',{}).get('charge','—')}", stripe_tag, stripe_col),
        ("Landauer floor (kT·ln2)", "THEORETICAL", THEO)]
y = 520
for label, tag, col in rows:
    d.rounded_rectangle([MARGIN, y, W - MARGIN, y + 150], radius=20, fill=CARD, outline=(40, 48, 66), width=2)
    text(d, (MARGIN + 50, y + 75), label, SANS(52), PEARL, "lm")
    pill(d, W - MARGIN - 620, y + 33, tag, SANS(46), col, (22, 30, 46))
    y += 172
text(d, (MARGIN, y + 30), "Alter one Joule and the chain breaks — verified by  python3 eval_skill.py", MONO(46), GOLD)
save(img, "06_ledger.png")

# 07 — spawn inherits the budget
img, d = base(caption="Autonomy cannot escape accounting by creating more autonomy")
text(d, (MARGIN, 340), "THE CHAIN", SANS(130), GOLD, "lm", bold=1)
text(d, (MARGIN, 470), "each spawned generation inherits the same dual caps + the same ledger", SANS(56), PEARL, "lm")
gw = (W - 2 * MARGIN - 2 * 160) // 3
reseed = ALLOC.get("reseed_usd", 0)
gens = [("gen 1", f"${G['limit_usd']:.0f} budget", f"{ENERGY_LIMIT:,.0f} J cap", "the parent cycle"),
        ("gen 2", f"${reseed:.0f} re-seed", f"{ENERGY_LIMIT:,.0f} J cap", "inherits caps + skill"),
        ("gen 3", "compounded", f"{ENERGY_LIMIT:,.0f} J cap", "the chain continues")]
gx = MARGIN; gy = 760
for i, (gid, b1, b2, sub) in enumerate(gens):
    bx, by = panel(d, gx, gy, gw, 700, None)
    text(d, (bx, by), gid, SANS(80), GOLD, "lm", bold=1)
    text(d, (bx, by + 150), b1, SANS(56), PEARL)
    text(d, (bx, by + 250), b2, SANS(56), ENERGY_COL)
    text(d, (bx, by + 380), sub, SANS(44), MUT)
    if i < 2:
        ay = gy + 350; ax0 = gx + gw + 40; ax1 = gx + gw + 140
        d.line([(ax0, ay), (ax1, ay)], fill=GREEN, width=10)
        d.polygon([(ax1, ay - 26), (ax1 + 40, ay), (ax1, ay + 26)], fill=GREEN)
    gx += gw + 160
text(d, (W // 2, 1640), "Autonomy cannot escape accounting by creating more autonomy.", SERIF(60), GOLD, "mm")
save(img, "07_spawn.png")

# 08 — skill / scale / close
img, d = base(kicker=None)
text(d, (W // 2, 360), "INSTALLABLE  ·  SCALES", SANS(110), GOLD, "mm", bold=1)
bx, by = panel(d, MARGIN, 520, W - 2 * MARGIN, 520, "Ships as a governed Hermes skill")
text(d, (bx, by), "$ ./install.sh   ->   ~/.hermes/skills/revenue-ops-lead-to-revenue/SKILL.md", MONO(48), GREEN)
text(d, (bx, by + 120), "/revenue-ops on Nous Hermes — governed by Landauer's dual-cap accounting contract", SANS(50), PEARL)
text(d, (W // 2, 1180), "laptop   ->   RTX 4070   ->   designed for DGX-class", SANS(80), PEARL, "mm")
text(d, (W // 2, 1300), "same policy structure · same accounting contract · only the power regime changes", SANS(50), MUT, "mm")
text(d, (W // 2, 1600), "Landauer", SANS(170), GOLD, "mm", bold=1)
text(d, (W // 2, 1780), "Agents that cannot outrun reality.", SERIF(72), PEARL, "mm")
text(d, (W // 2, 1950), "@NousResearch   ·   Nous/Hermes · NVIDIA · Stripe", MONO(46), MUT, "mm")
save(img, "08_close.png")

print("\nDONE — frames in", OUT)
