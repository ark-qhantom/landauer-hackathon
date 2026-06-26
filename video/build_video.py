#!/usr/bin/env python3
"""Two-stage assembly: (1) build each scene clip with a canonical Ken-Burns zoompan,
(2) xfade-crossfade the clips into a 1080p silent cut for voiceover. Landauer 8-beat spine."""
import os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.join(HERE, "frames")
CLIPS = os.path.join(HERE, "clips"); os.makedirs(CLIPS, exist_ok=True)
OUT = os.path.join(HERE, "landauer-demo.mp4")
FPS = 30
T = 1.0  # crossfade seconds

# (frame, seconds) — Beat 4 (REAL telemetry) is the longest, most-memorable beat per the thesis.
SCENES = [
    ("01_open.png", 12),        # cold open / the problem
    ("02_capability.png", 14),  # capability gate (PENDING)
    ("03_approval.png", 14),    # approval changes the run
    ("04_telemetry.png", 22),   # REAL telemetry (∫P·dt) — judge-decider
    ("05_twocaps.png", 18),     # two independent hard caps + orthogonal energy BLOCK
    ("06_ledger.png", 18),      # Reality Ledger + tamper (+ Stripe ids)
    ("07_spawn.png", 14),       # spawn inherits the budget
    ("08_close.png", 12),       # skill / scale / close
]
durs = [d for _, d in SCENES]
n = len(SCENES)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR:\n", r.stderr[-2000:]); raise SystemExit(1)
    return r


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


# ---- Stage 1: per-scene Ken-Burns clips ----
print("Stage 1 — scene clips:")
clip_paths = []
for i, (f, d) in enumerate(SCENES):
    frames = d * FPS
    inc = 0.08 / frames
    vf = (f"scale=3840:2160,zoompan=z='min(zoom+{inc:.6f},1.08)':d={frames}:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS},format=yuv420p")
    out = os.path.join(CLIPS, f"clip_{i:02d}.mp4")
    run(["ffmpeg", "-y", "-loop", "1", "-i", os.path.join(FR, f), "-vf", vf,
         "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), out])
    dd = probe_dur(out)
    print(f"  clip_{i:02d}  {f:<20} target {d}s  actual {dd:.2f}s  {'OK' if abs(dd-d) < 0.3 else 'MISMATCH'}")
    clip_paths.append(out)

# ---- Stage 2: xfade crossfade chain ----
print("Stage 2 — crossfade + silent audio track (for VO):")
inputs = []
for p in clip_paths:
    inputs += ["-i", p]
inputs += ["-f", "lavfi", "-t", str(sum(durs)), "-i", "anullsrc=r=48000:cl=stereo"]

fc = []
prev = "0:v"
for k in range(1, n):
    off = sum(durs[:k]) - k * T
    out = f"x{k}"
    fc.append(f"[{prev}][{k}:v]xfade=transition=fade:duration={T}:offset={off:.3f}[{out}]")
    prev = out
filtergraph = ";".join(fc)

total = sum(durs) - (n - 1) * T
print(f"  total ≈ {total:.0f}s ({int(total//60)}:{int(total % 60):02d})")
run(["ffmpeg", "-y", *inputs, "-filter_complex", filtergraph,
     "-map", f"[{prev}]", "-map", f"{n}:a",
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
     "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", OUT])
print("wrote", OUT, f"({probe_dur(OUT):.1f}s)")
