# Landauer — Demo Video Script (v3 — pipeline built, renders clean)

> **Pipeline status:** `make_frames.py` + `build_video.py` ported & rewritten for these 8 beats. The current
> MODELED dev-box run renders all 8 frames with no tofu/overflow and assembles to **`landauer-demo.mp4` (1:57)**.
> Frames auto-read `submission-artifacts/real-run-4070/` once it exists → Beats 4/5/6 flip to REAL with no edits.
> Frame map: `01_open · 02_capability · 03_approval · 04_telemetry · 05_twocaps · 06_ledger · 07_spawn · 08_close`.
> Beat 4 headline is source-aware: **METERED JOULES** (MODELED dev box) → **REAL JOULES** (4070). Pillow fonts
> lack the `→` glyph, so frames use drawn arrows / `->` (the dashboard HTML keeps `→`).


**Working title:** *Landauer: Agents That Cannot Outrun Reality*
**Target:** 1:45–2:15 · **Tag:** @NousResearch · **Palette:** indigo / pearl / gold
**Closing line:** "Landauer. Agents that cannot outrun reality."

## Killer claim (the logline)
> We built an agent runtime where **every action has a reality label, a hash-chained receipt, and an energy budget
> it cannot lie about.** Not "agents can spend money / call tools / spawn children" — a **trust substrate for
> autonomous systems.**

## Narrative arc — one question
**If agents are going to act in the world, what keeps them honest?** Answer = four constraints:
1. **Reality labels** — every action/number is REAL, MODELED, THEORETICAL, or BLOCKED (see honesty note on "DRY-RUN").
2. **Capability gates** — the agent cannot spend / mutate / call real systems unless a human approves (soft: approval clears).
3. **Energy-aware execution** — work is tracked against an energy budget, first MODELED, then MEASURED on real hardware.
4. **Hash-chained Reality Ledger** — every step is tamper-evident, energy columns included.

---

## Numbers to fill from the 4070 capture (script VO must match captured artifacts)
- Run shape (verified today): **4 auto-allowed · 6 capability-gated (PENDING) · 2 hard-BLOCKED**; approving all 6 → 6 HUMAN-APPROVED, **2 still BLOCKED**.
- Money cap `$300`; energy cap `<CAP_J>` (recalibrate on 4070; 50,000 J placeholder). `gpu-render-batch`: `~$5` (under money), projected `<PROJ_J>` ≥ cap → energy-BLOCKED.
- REAL measured cycle energy `<MEAS_J> J`, avg `<AVG_W> W`, peak `<PEAK_C> °C`; physics: Kepler `<STEPS>` steps, energy band `~2e-6`, L-drift `~1e-13`, `<STEPS/J> steps/J`.
- Stripe verifiable ids `prod_… / price_… / pi_… / ch_…` from the real test-mode charge.

---

## 8-beat spine (from the thesis)

| # | Beat | ~Time | On screen (source) | VO (draft) |
|---|------|-------|--------------------|------------|
| 1 | **Cold open — the problem** | 0:00–0:15 | Black → boot banner `LANDAUER — Physics-Grounded Agent Treasury` → killer-claim card. | "We're handing agents real money, real tools, real power draw — and almost no way to know what they actually did. What keeps an autonomous agent honest?" |
| 2 | **First hard stop (capability)** | 0:15–0:38 | Governance panel: 6 actions **PENDING** — gated. Highlight a spend/billing/credentials row. | "The agent goes to spend, to activate billing, to touch credentials — and it's stopped. Those capabilities are gated. It cannot act on the real world without a human. Status: PENDING." |
| 3 | **Approval changes the run** | 0:38–0:58 | Re-run with `--approve`: the 6 flip **PENDING → HUMAN-APPROVED**; labels visibly change. | "A human approves. The labels flip — pending to human-approved — and the agent is cleared to act. Approval decides *what runs*. Watch what it can't move." |
| 4 | **REAL telemetry — the judge-decider** | 0:58–1:25 | **(LONGEST, most memorable.)** Split screen: live `nvidia-smi` terminal **next to** the dashboard Energy panel — gold power sparkline (shaded area = ∫P·dt), pill **REAL · nvidia-smi**. (4070 run JSON + raw nvidia-smi) | "This is not a model. Same instant, two views: raw nvidia-smi on the left, Landauer's ledger on the right. Real watts, integrated to real Joules. The shaded area *is* the energy this agent spent." |
| 5 | **Two independent caps + the orthogonal energy BLOCK** | 1:25–1:48 | Energy Governance hero: dual USD+Joules P&L; the `gpu-render-batch` BLOCK row + caption **"money would have allowed it ($5 ≤ $300); the physics cap refused it."** Note: this action was *approved* and *within budget*. | "Two caps approval cannot touch. This action is approved and well inside its dollar budget — but it would burn past the energy budget. Money would have allowed it. Physics refused it." |
| 6 | **Reality Ledger + tamper detection** | 1:48–2:05 | Reality Ledger matrix (REAL/MODELED/THEORETICAL/SIMULATED incl. energy rows) → pan the hash-chained ledger `Energy (J)` column → cut to `eval_skill.py` tamper line: alter one Joule, chain breaks. | "Every step is a SHA-256-chained receipt — energy columns inside the chain. Change a single Joule, and every row after it breaks. The ledger can't be quietly edited." |
| 7 | **Spawn inherits the budget** | 2:05–2:15 | Agent Company Chain: gen 1 → 2 → 3; "energy budget inherited down the chain" (spawned-cofounder.yaml). | "It spawns the next generation — which inherits the same caps and the same ledger. Autonomy cannot escape accounting by creating more autonomy." |
| 8 | **Skill / scale + close** | 2:15–2:22 | Installable `SKILL.md` + `./install.sh`; regime card: laptop → **this 4070** → designed for DGX-class (same policy + accounting contract). | "Ships as an installable Hermes skill. The same policy structure and accounting contract runs on a laptop, on this 4070, and is built for DGX-class hardware. **Landauer. Agents that cannot outrun reality.**" |

*(Runs ~2:22; trim Beat 7 to a single chain sweep and tighten Beat 8 to land ≤ 2:15 if needed.)*

---

## Strongest proof beats (give them the most screen time)
- **Beat 4** (REAL nvidia-smi side-by-side) — longest, most memorable; it's the NVIDIA hero and the credibility anchor.
- **Beat 5** (orthogonal energy-only BLOCK) and **Beat 6** (tamper detection) — the two strongest *proof* moments.

## Honesty / overclaim guardrails (binding — Reality Ledger rules)
- **REAL** appears **only** for `nvidia-smi` telemetry from the 4070 run; the Mac rehearsal is **MODELED** and must be labeled so on screen. Never cut MODELED footage under a "REAL" pill.
- **No DGX overclaim:** Beat 8 says "**same policy structure and accounting contract**" / "designed for DGX-class" — **never** "we ran on a DGX." No measured DGX numbers exist.
- Landauer kT·ln2 floor stays **THEORETICAL** (annotation only); never implied to drive a block.
- Beat 3 phrasing — "approval changes the run" is honest as *approval changes what's cleared to execute* (PENDING→APPROVED). It does **not** change the energy accounting or lift the hard caps (that's Beat 5's whole point). VO is written to say exactly that; do not let the edit imply approval moved the Joules.

## Reconciliation notes for the founder (decisions, not blockers)
- **Reality labels — "DRY-RUN": DONE.** Renamed SIMULATED→DRY-RUN everywhere it appears (dashboard `_status_pill`, Reality-Ledger rows, Stripe + Hermes status, CLI summary, footer vocabulary, and the frames). Fallback behavior is byte-identical — only the label changed. Decisions stay PENDING / HUMAN-APPROVED / AUTO-ALLOWED / BLOCKED.
- **"Capability" cap wording (Beat 5):** the two caps approval can't lift are **money (USD budget)** and **energy (Joules)**. The thesis sometimes frames the pair as "capability + energy"; the script keeps the strongest, true version — capability gates are the *soft* layer (approval clears, Beats 2–3), and the *hard* caps are money + energy (Beat 5). Confirm you're happy with that layering.

## Production notes (next chunk, post-capture)
- Port `~/protos/hackathon/video/` — `make_frames.py` (4K Pillow stills) + `build_video.py` (Ken-Burns + xfade, 1080p). Toolchain proven here (ffmpeg 8.1.1, Pillow 12.2.0). **Rewrite** the SCENES + frame renderers for the 8 beats above and repoint data to Landauer's `out/run-*/` (`energy-report.json`, `audit-ledger.json`). Protos frames are style reference only (money-only, no energy beats).
- Render Beats 4 & 5 from the **4070** run JSON (REAL pills); Beat 4's nvidia-smi side-by-side is a live screen capture during the canonical run; Beats 1,2,3,6,7,8 render from any run.
