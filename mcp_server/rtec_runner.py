"""
Thin Python wrapper around the two core RTEC pipeline operations:

    compile_event_description(app, rules=None)  -> wraps `swipl ... compileED/2`
    run_recognition(app, ...)                   -> wraps `swipl ... continuousQueries/2`

This module is **MCP-agnostic on purpose** (same convention as `discovery.py`):
it knows how to drive RTEC via subprocess and how to read RTEC's own output, and
nothing about the Model Context Protocol. The MCP server (`server.py`) is a thin
presentation layer on top. Keeping the logic here means it is unit-testable with a
plain `python -m mcp_server.rtec_runner` smoke run, with no transport in the way.

How RTEC actually runs (verified empirically, see DESIGN_GAPS.md):

  COMPILE  cwd = "execution scripts/"
           swipl -l ../src/compiler.prolog \
                 -g "compileED('<rules.prolog>',withoutOptimisation),halt."
           -> writes "compiled_rules.prolog" next to the input rules file.

  RUN      cwd = "execution scripts/"
           swipl -l continuousQueries.prolog \
                 -g "continuousQueries(<app>,[<params>]),halt."
           -> writes "<results_dir>/log-swi-<W>-<S>-csv-file-recognised-intervals.txt"

Error contract for COMPILE (this is the whole point of the tool as a feedback channel):
  * exit != 0           -> hard failure; `ERROR:` lines on stderr (syntax, missing file)
  * exit == 0 + Warning -> compiled, but suspicious. `Singleton variables` in particular
                           almost always means a typo'd predicate or an unbound variable,
                           i.e. a rule that compiles cleanly yet never fires.
  * exit == 0, no Warn  -> clean.
So exit code alone is NOT trustworthy: warnings are surfaced as first-class feedback.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

from .discovery import EXAMPLES, REPO_ROOT, _app_dir  # reuse path helpers (DRY)

EXEC_DIR = REPO_ROOT / "execution scripts"
DEFAULTS_TOML = EXEC_DIR / "defaults.toml"
COMPILER_REL = "../src/compiler.prolog"          # relative to EXEC_DIR
CONTINUOUS_QUERIES = "continuousQueries.prolog"  # relative to EXEC_DIR

COMPILE_TIMEOUT_S = 180
RUN_TIMEOUT_S = 600


# ── config ──────────────────────────────────────────────────────────────────────
def _app_config(app: str) -> dict:
    """Read the app's section from `execution scripts/defaults.toml`.

    The paths inside the TOML are written relative to EXEC_DIR (e.g. '../examples/..').
    We resolve them to absolute paths so the wrapper is robust to the caller's cwd.
    """
    if not DEFAULTS_TOML.exists():
        raise FileNotFoundError(f"defaults.toml not found at {DEFAULTS_TOML}")
    with DEFAULTS_TOML.open("rb") as fh:
        cfg = tomllib.load(fh)
    if app not in cfg:
        raise ValueError(f"app '{app}' has no entry in defaults.toml. "
                         f"available: {sorted(k for k in cfg if isinstance(cfg[k], dict))}")
    return cfg[app]


def _resolve(rel_path: str) -> Path:
    """Resolve a defaults.toml path (relative to EXEC_DIR) to an absolute Path."""
    p = Path(rel_path)
    return p if p.is_absolute() else (EXEC_DIR / p).resolve()


# ── agent workspace (gold isolation) ─────────────────────────────────────────────
# The canonical examples/<app>/resources/patterns/rules.prolog is the hand-authored
# REFERENCE event description — effectively the solution. The in-loop agent must never
# read, compile, or overwrite it (CLAUDE.md §7). Instead the agent gets its own
# sandbox under examples/<app>/workspace/, holding ONLY agent-authored artifacts:
#   workspace/rules.prolog            the rules the agent writes
#   workspace/compiled_rules.prolog   compiler output (next to the input)
#   workspace/results/                this run's recognised intervals
# Discovery (inspect_stream / inspect_background) reads dataset/csv and
# resources/auxiliary, which are legitimate domain inputs — NOT the reference rules.
def _workspace(app: str) -> Path:
    return _app_dir(app) / "workspace"


def _agent_rules_path(app: str) -> Path:
    """Absolute path to the AGENT's working rules file (never the reference)."""
    return _workspace(app) / "rules.prolog"


def _agent_compiled_path(app: str) -> Path:
    return _workspace(app) / "compiled_rules.prolog"


def _prolog_list(paths: list[Path]) -> str:
    """Render a Prolog list of single-quoted atoms: ['a','b']."""
    return "[" + ",".join(f"'{p}'" for p in paths) + "]"


# ── defined-fluent extraction (for read_rules / dedup in multi-turn) ──────────────
_DEF_HEAD_RE = re.compile(r"^\s*(?:initiatedAt|terminatedAt|holdsFor)\(\s*(\w+)", re.MULTILINE)


def _defined_fluents(text: str) -> list[str]:
    """The fluent functors defined by initiatedAt/terminatedAt/holdsFor heads in `text`."""
    return sorted(set(_DEF_HEAD_RE.findall(text)))


# ── tool 1: compile ──────────────────────────────────────────────────────────────
def compile_event_description(app: str, rules: str | None = None,
                              mode: str = "overwrite") -> dict:
    """
    Compile an event description with RTEC's compiler.

    Operates only on the agent's workspace (examples/<app>/workspace/) — it never reads
    or writes the reference rules.prolog. If `rules` text is given it is the agent's
    *write* path; `mode` controls how:
      - "overwrite" (default): replace the workspace program with `rules`.
      - "append": add `rules` to the end of the existing workspace program. Use this in
        multi-turn synthesis to grow ONE event description fluent by fluent (reusing
        previously-defined fluents). The WHOLE accumulated program is then recompiled.
    If `rules` is omitted, the current workspace program is recompiled as-is.

    Returns a structured dict:
      { app, status, rules_file, compiled_file, errors[], warnings[], raw, returncode }
    where status is one of "success" | "success_with_warnings" | "error".
    """
    if mode not in ("overwrite", "append"):
        return {
            "app": app, "status": "error", "rules_file": None, "compiled_file": None,
            "errors": [f"invalid mode '{mode}'. use 'overwrite' or 'append'."],
            "warnings": [], "raw": "", "returncode": None,
        }
    _app_dir(app)  # validate app exists; raises with available list otherwise
    rules_file = _agent_rules_path(app)

    if rules is not None:
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append" and rules_file.exists():
            existing = rules_file.read_text().rstrip()
            rules_file.write_text(existing + "\n\n% ── appended fluent ──\n" + rules + "\n")
        else:
            rules_file.write_text(rules)

    if not rules_file.exists():
        return {
            "app": app, "status": "error", "rules_file": str(rules_file),
            "compiled_file": None,
            "errors": [f"no agent rules in workspace yet ({rules_file}). "
                       f"Call rtec_compile with the `rules` text to write them first."],
            "warnings": [], "raw": "", "returncode": None,
        }

    goal = f"compileED('{rules_file}',withoutOptimisation),halt."
    try:
        proc = subprocess.run(
            ["swipl", "-l", COMPILER_REL, "-g", goal],
            cwd=EXEC_DIR, capture_output=True, text=True, timeout=COMPILE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {
            "app": app, "status": "error", "rules_file": str(rules_file),
            "compiled_file": None,
            "errors": [f"compilation timed out after {COMPILE_TIMEOUT_S}s"],
            "warnings": [], "raw": "", "returncode": None,
        }

    combined = (proc.stdout or "") + (proc.stderr or "")
    errors = [ln.strip() for ln in combined.splitlines() if ln.startswith("ERROR:")]
    warnings = [ln.strip() for ln in combined.splitlines() if ln.startswith("Warning:")]
    compiled_file = rules_file.parent / "compiled_rules.prolog"

    if proc.returncode != 0 or errors:
        return {
            "app": app, "status": "error", "rules_file": str(rules_file),
            "compiled_file": None, "errors": errors, "warnings": warnings,
            "raw": combined.strip(), "returncode": proc.returncode,
        }

    compiled = str(compiled_file) if compiled_file.exists() else None

    # Degenerate-compile check. The compiler DERIVES cachingOrder2/2 (the fluent
    # processing order) from the grounding/1 + dynamicDomain declarations. If the
    # program omits those, the compiler emits zero cachingOrder2/2 clauses, the compile
    # still "succeeds", but rtec_run then crashes with "Unknown procedure:
    # cachingOrder2/2". Catch it here and turn that cryptic runtime crash into an
    # actionable compile-time diagnostic (this is the gap-#4 boilerplate trap).
    if compiled and "cachingOrder2(" not in compiled_file.read_text():
        warnings = warnings + [
            "Diagnostic: 0 output entities derived (no cachingOrder2/2). The program "
            "compiled but defines nothing runnable — rtec_run will fail. Add grounding/1 "
            "declarations for every fluent you define AND for the input events they use, "
            "plus dynamicDomain/1 for the entity domains."
        ]

    status = "success_with_warnings" if warnings else "success"
    return {
        "app": app, "status": status, "rules_file": str(rules_file),
        "compiled_file": compiled, "errors": errors, "warnings": warnings,
        "raw": combined.strip(), "returncode": proc.returncode,
    }


# ── tool 1b: read the agent's current program ────────────────────────────────────
def read_rules(app: str) -> dict:
    """
    Read the agent's CURRENT workspace event description (never the reference). In a
    multi-turn build this is the source of truth for what is already defined — use it to
    reuse existing fluents and avoid redefining them before appending a new one.

    Returns { app, exists, rules_file, rules, defined_fluents[], char_count }.
    """
    _app_dir(app)
    rules_file = _agent_rules_path(app)
    if not rules_file.exists():
        return {"app": app, "exists": False, "rules_file": str(rules_file),
                "rules": "", "defined_fluents": [], "char_count": 0}
    text = rules_file.read_text()
    return {"app": app, "exists": True, "rules_file": str(rules_file),
            "rules": text, "defined_fluents": _defined_fluents(text),
            "char_count": len(text)}


# ── tool 2: run ──────────────────────────────────────────────────────────────────
_REC_RE = re.compile(r"recognitions\(\w+,\s*(?P<fluent>\w+),")


def _result_file(results_dir: Path, window, step, input_mode="csv", output_mode="file") -> Path:
    """Reconstruct RTEC's result filename (see handleApplication.prolog add_info/4).

    Pattern: log-<prolog>-<window>-<step>-<inputmode>-<outputmode>-recognised-intervals.txt
    The Prolog atom for SWI is 'swi'.
    """
    name = f"log-swi-{window}-{step}-{input_mode}-{output_mode}-recognised-intervals.txt"
    return results_dir / name


def run_recognition(
    app: str,
    start_time: int | None = None,
    end_time: int | None = None,
    window: int | None = None,
    step: int | None = None,
    fluent: str | None = None,
    max_recognitions: int = 200,
) -> dict:
    """
    Run RTEC recognition on the (already compiled) event description and return the
    agent's *own* recognised intervals.

    start_time/end_time/window/step override the app defaults — use them to bound the
    run to a small slice; on big streams (maritime spans ~6 months) an unbounded run
    is slow and will hit the timeout. `fluent` filters the returned recognitions to a
    single target complex event.

    Returns:
      { app, status, result_file, window, step, start_time, end_time,
        fluents_present[], total_recognitions, returned, recognitions[],
        stats, errors[] }
    """
    _app_dir(app)
    cfg = _app_config(app)

    W = window if window is not None else cfg["window_size"]
    S = step if step is not None else cfg["step"]
    ST = start_time if start_time is not None else cfg["start_time"]
    ET = end_time if end_time is not None else cfg["end_time"]
    input_mode = cfg.get("input_mode", "csv")
    output_mode = cfg.get("output_mode", "file")
    stream_rate = cfg.get("stream_rate", 1)

    # event_description_files for the RUN = the AGENT's compiled rules + the app's
    # background knowledge (thresholds, static-data loaders — legitimate domain inputs,
    # not the reference solution). The agent's compiled rules come from the workspace,
    # never the reference compiled_rules.prolog.
    compiled = _agent_compiled_path(app)
    if not compiled.exists():
        return {
            "app": app, "status": "error", "result_file": None, "window": W, "step": S,
            "start_time": ST, "end_time": ET, "fluents_present": [], "total_recognitions": 0,
            "returned": 0, "recognitions": [], "stats": {},
            "errors": [f"no compiled agent rules at {compiled} — call rtec_compile first"],
        }
    bg = [_resolve(p) for p in cfg.get("background_knowledge", [])]
    ed_files = _prolog_list([compiled] + bg)

    providers = _prolog_list([_resolve(p) for p in cfg["input_providers"]])
    # Agent's results stay in its workspace, separate from any reference run output.
    results_dir = _workspace(app) / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    params = (
        f"window_size={W}, step={S}, start_time={ST}, end_time={ET}, "
        f"event_description_files={ed_files}, input_mode={input_mode}, "
        f"input_providers={providers}, results_directory='{results_dir}', "
        f"nodynamicgrounding, stream_rate={stream_rate}"
    )
    goal = f"continuousQueries({app},[{params}]),halt."

    try:
        proc = subprocess.run(
            ["swipl", "-l", CONTINUOUS_QUERIES, "-g", goal],
            cwd=EXEC_DIR, capture_output=True, text=True, timeout=RUN_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {
            "app": app, "status": "error", "result_file": None, "window": W, "step": S,
            "start_time": ST, "end_time": ET, "fluents_present": [], "total_recognitions": 0,
            "returned": 0, "recognitions": [], "stats": {},
            "errors": [f"run timed out after {RUN_TIMEOUT_S}s — narrow the window with "
                       f"start_time/end_time"],
        }

    combined = (proc.stdout or "") + (proc.stderr or "")
    errors = [ln.strip() for ln in combined.splitlines() if ln.startswith("ERROR:")]
    if any("cachingOrder2" in e for e in errors):
        errors.append(
            "Hint: this means the compiled program has no output entities. Recompile "
            "with grounding/1 declarations for every fluent and input event (see "
            "rtec_compile's degenerate-compile diagnostic)."
        )

    result_file = _result_file(results_dir, W, S, input_mode, output_mode)
    if not result_file.exists():
        # fall back to newest matching file (e.g. unexpected output_mode)
        candidates = sorted(results_dir.glob("*recognised-intervals.txt"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        result_file = candidates[0] if candidates else None

    recognitions: list[str] = []
    fluents_present: set[str] = set()
    total = 0
    if result_file and result_file.exists():
        with result_file.open() as fh:
            for line in fh:
                line = line.rstrip("\n")
                m = _REC_RE.match(line)
                if not m:
                    continue
                fl = m.group("fluent")
                fluents_present.add(fl)
                if fluent is not None and fl != fluent:
                    continue
                total += 1
                if len(recognitions) < max_recognitions:
                    recognitions.append(line)

    stats = _parse_stats(combined)
    status = "error" if (errors or result_file is None) else "success"
    if status == "error" and not errors:
        errors = ["no result file was produced"]

    return {
        "app": app, "status": status,
        "result_file": str(result_file) if result_file else None,
        "window": W, "step": S, "start_time": ST, "end_time": ET,
        "fluents_present": sorted(fluents_present),
        "total_recognitions": total, "returned": len(recognitions),
        "recognitions": recognitions, "stats": stats, "errors": errors,
    }


def _parse_stats(log: str) -> dict:
    """Pull the average summary numbers RTEC prints to stdout."""
    stats: dict[str, str] = {}
    for line in log.splitlines():
        if ":" in line and "average" in line.lower():
            key, _, val = line.partition(":")
            stats[key.strip()] = val.strip()
    return stats


if __name__ == "__main__":
    import json
    print("=== compile toy ===")
    print(json.dumps(compile_event_description("toy"), indent=2))
    print("\n=== run toy ===")
    print(json.dumps(run_recognition("toy"), indent=2))
