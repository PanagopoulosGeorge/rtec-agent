# RTEC Authoring Guide — Task Wrapper

The standing procedure wrapped around the user's NL description. Variables `{{APP}}` and
`{{NL_DESCRIPTION}}` are filled by the harness / MCP prompt. Delivered after `rtec_core.md`
and `domains/{{APP}}.md`.

---

You synthesize ONE composite-activity definition in the RTEC language for the `{{APP}}`
application, then verify it by running RTEC and refine until it is non-degenerate. The
RTEC authoring guide (language, mandatory declarations, interval semantics) and the
`{{APP}}` domain signature are in your context. The reference solution is hidden — write a
COMPLETE, self-contained program into your isolated workspace.

Available tools:
- `inspect_stream(app, event_type?, entity?, t_from?, t_to?)` — discover events/entities/values.
- `inspect_background(app, pattern)` — discover thresholds, types, helper predicates.
- `rtec_compile(app, rules)` — write + compile (read errors AND warnings).
- `rtec_run(app, start_time?, end_time?, window?, step?, fluent?)` — your own recognitions.

Procedure:
1. Determine the target fluent: arguments, value(s), and whether it is a SIMPLE fluent
   (`initiatedAt`/`terminatedAt`) or STATICALLY DETERMINED (`holdsFor` + interval ops).
2. List every sub-activity it depends on. For each dependency that is itself a composite
   fluent, DEFINE IT TOO — recurse until everything bottoms out at input events/fluents
   and background predicates (whole-program synthesis).
3. Discover exact event names, argument shapes, thresholds, and entity domains via
   `inspect_stream` / `inspect_background`. Never guess a name or a threshold value.
4. Write a COMPLETE program: all rules + `grounding/1` for EVERY fluent you define and
   EVERY input event you use + `dynamicDomain` for stream-derived entities (+ `fi/3`,
   `p/1` if a deadline / auto-termination is implied).
5. `rtec_compile`. Fix all errors. Treat singleton-variable warnings and the
   "0 output entities (no cachingOrder2)" diagnostic as MUST-FIX bugs.
6. `rtec_run` on a small bounded window. Check: is the target fluent in `fluents_present`?
   non-empty? not stuck-on-forever? Are interval boundaries consistent with the stream
   events you used (allowing RTEC's `+1` offset)?
7. If degenerate or inconsistent, diagnose (missing grounding? wrong event name? wrong
   threshold? missing dependency?) and refine. Repeat.
8. Stop when the target compiles cleanly and produces non-degenerate, stream-consistent
   recognitions.

TARGET COMPOSITE ACTIVITY:
{{NL_DESCRIPTION}}
