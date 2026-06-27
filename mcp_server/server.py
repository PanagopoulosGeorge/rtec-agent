"""
RTEC MCP server (stdio).

Thin presentation layer over the pure-Python wrappers in `rtec_runner.py`. The
server's only jobs are: name the tools, describe them well enough that an LLM client
picks the right one with the right arguments, declare behavioural hints, and hand the
structured result back. All actual work lives in `rtec_runner` / `discovery`.

Run it:
    .venv/bin/python -m mcp_server.server
Inspect it:
    npx @modelcontextprotocol/inspector .venv/bin/python -m mcp_server.server

Tools exposed so far (the two core pipeline wrappers):
    rtec_compile(app, rules=None)
    rtec_run(app, start_time=, end_time=, window=, step=, fluent=, max_recognitions=)
The discovery tools (inspect_stream / inspect_background) live in discovery.py and
will be registered here in a later step.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# Dual-mode import: relative works under `python -m mcp_server.server`; the fallback
# covers `mcp dev mcp_server/server.py` / the Inspector, which load this file by path
# (no parent package). Putting the repo root on sys.path lets us import the package so
# rtec_runner's own `from .discovery import ...` keeps working too.
try:
    from .context import build_synthesis_prompt, load_core, load_domain
    from .discovery import inspect_background, inspect_stream
    from .rtec_runner import compile_event_description, read_rules, run_recognition
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from mcp_server.context import build_synthesis_prompt, load_core, load_domain
    from mcp_server.discovery import inspect_background, inspect_stream
    from mcp_server.rtec_runner import compile_event_description, read_rules, run_recognition

mcp = FastMCP("rtec")


@mcp.tool(
    name="rtec_compile",
    description=(
        "Compile an RTEC event description (the initiatedAt/terminatedAt/holdsFor "
        "rules) with RTEC's Prolog compiler. This is also the WRITE path: pass the "
        "rule text in `rules` to write the agent's working rules and compile them in "
        "one step; omit `rules` to recompile the agent's current workspace rules. "
        "`mode='overwrite'` (default) replaces the program; `mode='append'` adds `rules` "
        "to the existing program — use append to build ONE event description across "
        "turns, reusing fluents you defined earlier (call read_rules first to see them). "
        "Operates only in the agent's isolated workspace — it never reads or writes "
        "the held-out reference event description.\n\n"
        "IMPORTANT: a successful exit code does NOT mean the rules are correct. RTEC "
        "compiles a rule with a typo'd predicate or an unbound variable without error "
        "— it just never fires. Always read the `warnings` field: 'Singleton "
        "variables' almost always signals a misspelled predicate or a logic bug.\n\n"
        "Returns status ('success' | 'success_with_warnings' | 'error'), the path to "
        "compiled_rules.prolog, and the `errors`/`warnings` lines from the compiler. "
        "On 'error' (e.g. a syntax error) the message includes file:line:column."
    ),
    annotations=ToolAnnotations(
        title="Compile RTEC event description",
        readOnlyHint=False,      # writes rules + compiled_rules.prolog
        destructiveHint=False,   # only overwrites the agent's own working files
        idempotentHint=True,     # same rules -> same compiled output
        openWorldHint=False,
    ),
)
def rtec_compile(app: str, rules: str | None = None, mode: str = "overwrite") -> dict:
    """
    Args:
        app: target application (e.g. "maritime", "toy").
        rules: optional event-description text to write before compiling. If omitted,
            the current workspace program is recompiled as-is.
        mode: "overwrite" (default) replaces the workspace program; "append" adds `rules`
            to the existing program (for multi-turn, fluent-by-fluent building).
    """
    return compile_event_description(app, rules=rules, mode=mode)


@mcp.tool(
    name="read_rules",
    description=(
        "Read the agent's CURRENT workspace event description (never the held-out "
        "reference). In multi-turn synthesis this is the source of truth for what is "
        "already defined: call it before adding a new fluent so you can REUSE existing "
        "fluents (reference them in holdsFor/holdsAt) instead of redefining them, and "
        "merge declarations (e.g. dynamicDomain) without duplication.\n\n"
        "Returns the full program text, `defined_fluents` (the fluent functors already "
        "defined), and `exists`/`char_count`."
    ),
    annotations=ToolAnnotations(
        title="Read current workspace rules",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def read_rules_tool(app: str) -> dict:
    """
    Args:
        app: target application (e.g. "maritime").
    """
    return read_rules(app)


@mcp.tool(
    name="rtec_run",
    description=(
        "Run RTEC recognition over the input event stream using the ALREADY-COMPILED "
        "event description, and return the agent's OWN recognised intervals (no gold, "
        "no comparison). Call rtec_compile first.\n\n"
        "Bound the run with start_time/end_time (and optionally window/step) — the "
        "maritime stream spans ~6 months and an unbounded run is slow and may time "
        "out. Use `fluent` to return only the intervals of one target complex event; "
        "`fluents_present` always lists every fluent the run produced.\n\n"
        "Returns the result-file path, `fluents_present`, `total_recognitions` (for the "
        "filtered fluent), up to `max_recognitions` raw recognition terms, and run "
        "`stats`. A degenerate result (a target fluent absent from `fluents_present`, "
        "or zero recognitions) is the never-fires signal for self-supervised feedback."
    ),
    annotations=ToolAnnotations(
        title="Run RTEC recognition",
        readOnlyHint=False,      # writes a results file
        destructiveHint=False,
        idempotentHint=True,     # same compiled rules + window -> same intervals
        openWorldHint=False,
    ),
)
def rtec_run(
    app: str,
    start_time: int | None = None,
    end_time: int | None = None,
    window: int | None = None,
    step: int | None = None,
    fluent: str | None = None,
    max_recognitions: int = 200,
) -> dict:
    """
    Args:
        app: target application (e.g. "maritime", "toy").
        start_time: first timestamp to reason over (overrides the app default).
        end_time: last timestamp to reason over (overrides the app default).
        window: temporal window size in seconds (overrides the app default).
        step: query step in seconds (overrides the app default).
        fluent: if set, return only recognitions of this fluent (e.g. "gap").
        max_recognitions: cap on the number of raw recognition terms returned.
    """
    return run_recognition(
        app, start_time=start_time, end_time=end_time, window=window, step=step,
        fluent=fluent, max_recognitions=max_recognitions,
    )


@mcp.tool(
    name="inspect_stream",
    description=(
        "Discover what is in the input event stream (the agent's window into the "
        "domain — there is no curated vocabulary). With NO filters, returns a SUMMARY "
        "over the first `max_scan` lines: which event types exist (with counts), how "
        "many distinct entities, and the time range. With filters (event_type / entity "
        "/ t_from / t_to) returns up to `limit` matching raw events (streamed, "
        "early-exit, so cheap even on the ~16M-line maritime file).\n\n"
        "Records are pipe-delimited: <event_type>|<arrival_t>|<occur_t>|<entity>|"
        "<arg1>|...  Use this to find the instantaneous events that initiate/terminate "
        "a target fluent (e.g. slow_motion_start/end for lowSpeed) before writing rules."
    ),
    annotations=ToolAnnotations(
        title="Inspect input event stream",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def inspect_stream_tool(
    app: str,
    event_type: str | None = None,
    entity: str | int | None = None,
    t_from: int | None = None,
    t_to: int | None = None,
    limit: int = 50,
) -> str:
    """
    Args:
        app: target application (e.g. "maritime").
        event_type: filter to one event type (e.g. "velocity", "slow_motion_start").
        entity: filter to one entity id (e.g. a vessel MMSI).
        t_from: only events with occurrence time >= this.
        t_to: only events with occurrence time <= this.
        limit: max matching events to return in filtered mode.
    """
    return inspect_stream(app, event_type=event_type, entity=entity,
                          t_from=t_from, t_to=t_to, limit=limit)


@mcp.tool(
    name="inspect_background",
    description=(
        "Grep the auxiliary / static-data Prolog files that RTEC loads as background "
        "knowledge (thresholds, area types, vessel types/speeds, port statuses, and "
        "helper-predicate definitions like oneIsTug/absoluteAngleDiff). This is how the "
        "agent discovers named thresholds and entity domains WITHOUT a curated "
        "vocabulary file — it greps the same inputs RTEC itself uses. Does NOT reach "
        "the reference event description (that lives in resources/patterns, not "
        "auxiliary).\n\n"
        "Examples: inspect_background('maritime', 'thresholds'); "
        "inspect_background('maritime', 'vesselType'); "
        "inspect_background('maritime', 'areaType')."
    ),
    annotations=ToolAnnotations(
        title="Inspect background/static-data files",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def inspect_background_tool(
    app: str, pattern: str, limit: int = 50, ignore_case: bool = True
) -> str:
    """
    Args:
        app: target application (e.g. "maritime").
        pattern: substring to grep for across the auxiliary Prolog files.
        limit: max matching lines to return.
        ignore_case: case-insensitive match (default true).
    """
    return inspect_background(app, pattern, limit=limit, ignore_case=ignore_case)


# ── authoring context (resources + a prompt) ─────────────────────────────────────
# The agent's "how to write RTEC" context is delivered three ways from one source
# (resources/authoring/), so it travels across MCP consumers:
#   - resource  rtec://authoring/core          the domain-agnostic guide
#   - resource  rtec://authoring/domain/{app}  a domain signature
#   - prompt    synthesize_fluent(app, nl)      core + domain + task wrapper + the NL
# Clients that don't consume resources/prompts can instead use context.build_synthesis_prompt
# directly as a system prompt (harness path).

@mcp.resource("rtec://authoring/core")
def authoring_core() -> str:
    """The domain-agnostic RTEC authoring guide (language, declarations, gotchas)."""
    return load_core()


@mcp.resource("rtec://authoring/domain/{app}")
def authoring_domain(app: str) -> str:
    """The per-domain signature (events, input fluents, background knowledge) for `app`."""
    return load_domain(app)


@mcp.prompt(
    name="synthesize_fluent",
    description=(
        "Full context for synthesizing ONE RTEC composite-activity (fluent) definition: "
        "the core authoring guide + the app's domain signature + the standing "
        "discover/compile/run/refine procedure, with the natural-language description "
        "filled in. Provide only `app` and the NL `nl_description`."
    ),
)
def synthesize_fluent(app: str, nl_description: str) -> str:
    """
    Args:
        app: target application (e.g. "maritime").
        nl_description: the natural-language description of the target composite activity.
    """
    return build_synthesis_prompt(app, nl_description)


if __name__ == "__main__":
    mcp.run(transport="stdio")
