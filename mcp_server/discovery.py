"""
Discovery tools for the unsupervised RTEC self-refinement layer.

These REPLACE the curated `get_vocabulary`. Instead of being handed the domain
signature, the agent DISCOVERS it by inspecting:
  - the raw event stream (what events / entities / value-ranges actually exist), and
  - the background/static-data Prolog files that RTEC itself loads (thresholds,
    area types, vessel types, helper-predicate signatures).

No ground truth, no curated vocabulary — just grep over the same inputs RTEC uses.

Two tools (to be exposed via MCP):
  inspect_stream(app, ...)        -> events / entities / value-ranges from the input CSV
  inspect_background(app, pattern) -> grep the auxiliary static-data Prolog files

Event-stream format (pipe-delimited):
  <event_type>|<start_t>|<end_t>|<entity>|<arg1>|<arg2>|...
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"


# ── path helpers ────────────────────────────────────────────────────────────────
def _app_dir(app: str) -> Path:
    d = EXAMPLES / app
    if not d.exists():
        avail = sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir())
        raise ValueError(f"unknown app '{app}'. available: {avail}")
    return d


def _csv_files(app: str) -> list[Path]:
    return sorted((_app_dir(app) / "dataset" / "csv").glob("*.csv"))


def _aux_files(app: str) -> list[Path]:
    return sorted((_app_dir(app) / "resources" / "auxiliary").rglob("*.prolog"))


# ── tool 1: inspect the event stream ────────────────────────────────────────────
def inspect_stream(
    app: str,
    event_type: str | None = None,
    entity: str | int | None = None,
    t_from: int | None = None,
    t_to: int | None = None,
    limit: int = 50,
    max_scan: int = 500_000,
) -> str:
    """
    Discover what is in the input stream.

    - No filters -> a SUMMARY over the first `max_scan` lines: which event types exist
      (with counts), how many distinct entities, and the time range.
    - With filters (event_type / entity / t_from / t_to) -> up to `limit` matching raw
      events (streamed, early-exit, so filtered queries are cheap even on huge files).
    """
    files = _csv_files(app)
    if not files:
        return f"no CSV input stream found for app '{app}'"

    entity = None if entity is None else str(entity)
    has_filter = any(x is not None for x in (event_type, entity, t_from, t_to))

    if has_filter:
        matches: list[str] = []
        for f in files:
            with f.open() as fh:
                for raw in fh:
                    parts = raw.rstrip("\n").split("|")
                    if len(parts) < 4:
                        continue
                    etype, st, _et, ent = parts[0], parts[1], parts[2], parts[3]
                    if event_type and etype != event_type:
                        continue
                    if entity and ent != entity:
                        continue
                    if t_from is not None or t_to is not None:
                        try:
                            ts = int(st)
                        except ValueError:
                            continue
                        if t_from is not None and ts < t_from:
                            continue
                        if t_to is not None and ts > t_to:
                            continue
                    matches.append(raw.rstrip("\n"))
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        head = (f"matching events (event_type={event_type}, entity={entity}, "
                f"t_from={t_from}, t_to={t_to}) — showing {len(matches)} (limit {limit}):")
        return head + "\n" + ("\n".join(matches) if matches else "  (none)")

    # summary mode
    counts: dict[str, int] = {}
    entities: set[str] = set()
    tmin = tmax = None
    scanned = 0
    for f in files:
        with f.open() as fh:
            for raw in fh:
                parts = raw.rstrip("\n").split("|")
                if len(parts) < 4:
                    continue
                counts[parts[0]] = counts.get(parts[0], 0) + 1
                if len(entities) < 100000:
                    entities.add(parts[3])
                try:
                    ts = int(parts[1])
                    tmin = ts if tmin is None else min(tmin, ts)
                    tmax = ts if tmax is None else max(tmax, ts)
                except ValueError:
                    pass
                scanned += 1
                if scanned >= max_scan:
                    break
        if scanned >= max_scan:
            break

    truncated = " (sampled — file larger than max_scan)" if scanned >= max_scan else ""
    lines = [
        f"stream summary for '{app}' over {scanned:,} lines{truncated}:",
        f"  files: {[f.name for f in files]}",
        f"  time range: {tmin} .. {tmax}",
        f"  distinct entities (in sample): {len(entities)}",
        "  event types (count):",
    ]
    for et, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"    {et:<24} {n:,}")
    return "\n".join(lines)


# ── tool 2: inspect the background / static-data files ──────────────────────────
def inspect_background(app: str, pattern: str, limit: int = 50, ignore_case: bool = True) -> str:
    """
    Grep the auxiliary/static-data Prolog files RTEC loads (thresholds, area types,
    vessel types, helper-predicate definitions). This is how the agent discovers the
    named thresholds / entity domains / available predicates — without a curated
    vocabulary file.

    Examples: inspect_background('maritime', 'thresholds')
              inspect_background('maritime', 'vesselType')
              inspect_background('maritime', 'areaType')
    """
    files = _aux_files(app)
    if not files:
        return f"no auxiliary background files found for app '{app}'"
    needle = pattern.lower() if ignore_case else pattern
    hits: list[str] = []
    for f in files:
        rel = f.relative_to(_app_dir(app))
        try:
            for i, raw in enumerate(f.open(), 1):
                line = raw.rstrip("\n")
                hay = line.lower() if ignore_case else line
                if needle in hay:
                    hits.append(f"{rel}:{i}: {line.strip()}")
                    if len(hits) >= limit:
                        break
        except (UnicodeDecodeError, OSError):
            continue
        if len(hits) >= limit:
            break
    head = f"background matches for '{pattern}' in app '{app}' — {len(hits)} (limit {limit}):"
    return head + "\n" + ("\n".join(hits) if hits else "  (none)")


if __name__ == "__main__":
    # smoke demo against maritime
    print("=== inspect_stream (summary) ===")
    print(inspect_stream("maritime", max_scan=200_000))
    print("\n=== inspect_stream (filtered: velocity for one vessel) ===")
    print(inspect_stream("maritime", event_type="velocity", entity="228854000", limit=3))
    print("\n=== inspect_background('thresholds') ===")
    print(inspect_background("maritime", "thresholds", limit=8))
    print("\n=== inspect_background('vesselType') ===")
    print(inspect_background("maritime", "vesselType", limit=5))
