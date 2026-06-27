#!/usr/bin/env python3
"""
External gold scoring for ONE fluent (host-side — NOT part of the agent loop).

Methodology: score the saved compiled ARTIFACTS over a controlled window. Re-runs the
agent's program (examples/<app>/workspace/compiled_rules.prolog) AND the held-out
reference (examples/<app>/resources/patterns/compiled_rules.prolog) over the SAME window,
filters both to <fluent>, and scores with `execution scripts/scoring/evaluate.py`
(interval/time-point precision/recall/F1). RTEC is deterministic, so this is reproducible
and independent of whatever ad-hoc windows the agent used during synthesis.

Run on the HOST (needs the full repo incl. the reference; the agent container deliberately
excludes it). Outputs land in build/score/<app>/ (gitignored).

Usage:
  python scripts/score_fluent.py --app maritime --fluent lowSpeed \
      --start 1443650401 --end 1443700000 --window 36000 --step 36000
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from mcp_server import rtec_runner as rr  # noqa: E402

SCORING_DIR = rr.EXEC_DIR / "scoring"


def _run(compiled: Path, results_dir: Path, app, W, S, ST, ET, cfg, bg, providers) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    ed = rr._prolog_list([compiled] + bg)
    params = (
        f"window_size={W}, step={S}, start_time={ST}, end_time={ET}, "
        f"event_description_files={ed}, input_mode=csv, input_providers={providers}, "
        f"results_directory='{results_dir}', nodynamicgrounding, stream_rate={cfg.get('stream_rate', 1)}"
    )
    goal = f"continuousQueries({app},[{params}]),halt."
    p = subprocess.run(["swipl", "-l", rr.CONTINUOUS_QUERIES, "-g", goal],
                       cwd=rr.EXEC_DIR, capture_output=True, text=True, timeout=rr.RUN_TIMEOUT_S)
    f = results_dir / f"log-swi-{W}-{S}-csv-file-recognised-intervals.txt"
    if p.returncode != 0 or not f.exists():
        raise RuntimeError(f"RTEC run failed (exit {p.returncode}):\n{(p.stderr or '')[-500:]}")
    return f


def _filter(src: Path, dst: Path, fluent: str) -> int:
    lines = [l for l in src.read_text().splitlines() if f",{fluent}," in l]
    dst.write_text("\n".join(lines) + "\n")
    return len(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", required=True)
    ap.add_argument("--fluent", required=True)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--window", type=int, default=None)
    ap.add_argument("--step", type=int, default=None)
    ap.add_argument("--out", default=None, help="report CSV path (default build/score/<app>/<fluent>_report.csv)")
    a = ap.parse_args()

    cfg = rr._app_config(a.app)
    W = a.window or cfg["window_size"]
    S = a.step or cfg["step"]
    ST = a.start if a.start is not None else cfg["start_time"]
    ET = a.end if a.end is not None else cfg["end_time"]
    bg = [rr._resolve(p) for p in cfg.get("background_knowledge", [])]
    providers = rr._prolog_list([rr._resolve(p) for p in cfg["input_providers"]])

    agent = rr._agent_compiled_path(a.app)
    ref = rr._resolve(cfg["event_description"]).parent / "compiled_rules.prolog"
    if not agent.exists():
        sys.exit(f"no agent compiled rules at {agent} — synthesize + rtec_compile first")
    if not ref.exists():
        sys.exit(f"no reference compiled rules at {ref} — compile the held-out reference first")

    base = REPO_ROOT / "build" / "score" / a.app
    test_f = _run(agent, base / "test", a.app, W, S, ST, ET, cfg, bg, providers)
    gold_f = _run(ref, base / "gold", a.app, W, S, ST, ET, cfg, bg, providers)

    tfilt, gfilt = base / f"{a.fluent}_test.txt", base / f"{a.fluent}_gold.txt"
    nt, ng = _filter(test_f, tfilt, a.fluent), _filter(gold_f, gfilt, a.fluent)
    out = Path(a.out) if a.out else base / f"{a.fluent}_report.csv"

    subprocess.run([sys.executable, "evaluate.py", "--gt", str(gfilt), "--test", str(tfilt),
                    "--out", str(out)], cwd=SCORING_DIR, check=True)

    print(f"\napp={a.app}  fluent={a.fluent}  window=({ST},{ET}]  W={W} S={S}")
    print(f"agent lines={nt}  gold lines={ng}")
    print("--- report ---")
    print(out.read_text())


if __name__ == "__main__":
    main()
