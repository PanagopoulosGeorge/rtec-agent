# RTEC Authoring Guide — Task Wrapper

The standing procedure wrapped around the user's NL description. Variables `{{APP}}` and
`{{NL_DESCRIPTION}}` are filled by the harness / MCP prompt. Delivered after `rtec_core.md`
and `domains/{{APP}}.md`.

---

You build ONE RTEC event description for the `{{APP}}` application **incrementally** — adding
one target fluent at a time and accumulating into a single growing program, reusing what you
have already defined. You verify each addition by running RTEC and refine until it is
non-degenerate. The RTEC authoring guide (language, mandatory declarations, interval
semantics) and the `{{APP}}` domain signature are in your context. The reference solution is
hidden — you write only into your own isolated workspace.

Available tools:
- `inspect_stream(app, event_type?, entity?, t_from?, t_to?)` — discover events/entities/values.
- `inspect_background(app, pattern)` — discover thresholds, types, helper predicates.
- `read_rules(app)` — your CURRENT workspace program + `defined_fluents` (what already exists).
- `rtec_compile(app, rules, mode)` — write + compile. `mode="append"` EXTENDS the program;
  `mode="overwrite"` replaces it. Read errors AND warnings.
- `rtec_run(app, start_time?, end_time?, window?, step?, fluent?)` — your own recognitions.

Incremental procedure — for EACH target fluent:
1. Call `read_rules` first. From `defined_fluents`, REUSE any fluent already defined (reference
   it in `holdsFor`/`holdsAt`); never redefine it.
2. Determine the target: arguments, value(s), and whether it is a SIMPLE fluent
   (`initiatedAt`/`terminatedAt`) or STATICALLY DETERMINED (`holdsFor` + interval ops).
3. List its dependencies. Define first any dependency fluent NOT yet in `defined_fluents`
   (recurse until everything bottoms out at input events/fluents and background predicates).
   Discover exact event names, argument shapes, thresholds and entity domains via
   `inspect_stream` / `inspect_background`. Never guess a name or a threshold value.
4. Add ONLY the new clauses with `rtec_compile(app, <new rules>, mode="append")` — extend the
   program; do not resend or overwrite what is already defined. Include `grounding/1` for
   every NEW fluent and input event, `dynamicDomain` for stream-derived entities (once — do
   not duplicate), and `fi/3`+`p/1` if a deadline/auto-termination is implied.
   Use `mode="overwrite"` ONLY to start a brand-new, empty program.
5. Fix all errors. Treat singleton-variable warnings and the "0 output entities (no
   cachingOrder2)" diagnostic as MUST-FIX bugs.
6. `rtec_run` on a small bounded window with `fluent=<this target>`. Check: present in
   `fluents_present`? non-empty? not stuck-on-forever? boundaries consistent with the stream
   events you used (allowing RTEC's `+1` offset)? Adding a fluent must NOT break earlier ones.
7. If degenerate or inconsistent, diagnose (missing grounding? wrong event name? wrong
   threshold? missing dependency?) and refine. Repeat.
8. When this fluent compiles cleanly and is non-degenerate, move on to the next target.

TARGET COMPOSITE ACTIVITY:
{{NL_DESCRIPTION}}
