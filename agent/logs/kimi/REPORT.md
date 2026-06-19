# Maritime Experiment Report — kimi 2.7

**Setup.** RTEC maritime domain (Brest AIS), **54h window** (`start_time=1443650401`,
`end_time=1443844801`), gold standard produced by the expert event description.
Synthesizer = **kimi 2.7** inside the CEGIS ReAct loop (compile → run RTEC → compare to gold →
leak-safe feedback), convergence threshold **τ = 0.95** (per-fluent F1), leak-free (gold intervals
never shown to the model).

**Evaluability caveat.** Several target fluents have too few gold instances in this 54h window to
be meaningfully scored. The instance counts below tier each fluent: **robust (≥ ~60)**,
**low-confidence (≤ ~10)**, **N/A (0)**. `tugging` has 0 gold instances and was not run.

---

## 1. Results — all fluents

| Fluent | Status | Best F1 | Gold | Tier |
|---|---|---|---|---|
| gap | ✅ CONVERGED | 1.00 | 1595 | robust |
| changingSpeed | ✅ CONVERGED | 1.00 | 312 | robust |
| lowSpeed | ✅ CONVERGED | 1.00 | 183 | robust |
| anchoredOrMoored | ✅ CONVERGED | 1.00 | 139 | robust (SD fluent) |
| highSpeedNearCoast | ✅ CONVERGED | 1.00 | 97 | robust |
| trawlSpeed | ✅ CONVERGED | 1.00 | 90 | robust |
| sarSpeed | ✅ CONVERGED | 1.00 | 3 | low-confidence |
| pilotOps | ✅ CONVERGED | 1.00 | 5 | low-confidence |
| trawlingMovement | ⚠️ STALLED | 0.70 | 110 | robust |
| movingSpeed | ⚠️ STALLED | 0.46 | 1111 | robust |
| loitering | ⚠️ STALLED | 0.44 | 63 | robust |
| sarMovement | ⚠️ STALLED | 0.40 | 10 | low-confidence |
| drifting | ⚠️ STALLED | 0.30 | 101 | robust |
| tuggingSpeed | ⛔ EXHAUSTED | 0.52 | 773 | robust |
| trawling | ⛔ EXHAUSTED | 0.52 | 3 | low-confidence |
| inSAR | ⛔ EXHAUSTED | 0.78 | 1 | low-confidence / N/A |

*(EXHAUSTED = ran out of the iteration budget without the convergence controller declaring a
terminal state; `trawlingMovement_stopped.log` is a re-run of `trawlingMovement`, same 0.70.)*

### Headline
Of the **11 robustly-evaluable fluents** (gold ≥ ~60): **6 reached exact behavioral equivalence
(F1 = 1.0)** — `gap`, `changingSpeed`, `lowSpeed`, `anchoredOrMoored`, `highSpeedNearCoast`,
`trawlSpeed` — all **without any leakage of the answer to the model**. The remaining 5 expose a
clear, citable **failure taxonomy** (§3). Two more (`sarSpeed`, `pilotOps`) converged but on too
few instances to count.

---

## 2. Converged fluents (F1 = 1.0)

These were synthesized honestly (none are few-shot-seeded; the few-shot examples cover
`withinArea`/`stopped`/`underWay` only):

- **gap, changingSpeed, lowSpeed, trawlSpeed, highSpeedNearCoast** — simple fluents, inferred
  correctly from the NL + vocabulary.
- **anchoredOrMoored** — a **statically-determined fluent** built with `holdsFor` +
  `intersect_all`/`union_all` + `intDurGreater`. Significant: the agent handled the harder SD
  fluent class, not just simple fluents.
- **highSpeedNearCoast** — the agent discovered the correct `gap_start` termination and `nearCoast`
  area type *on its own* (gpt-4o could not).

> Note: `sarSpeed` (3 gold) and `pilotOps` (5 gold) converged but are **low-confidence** — a
> handful of intervals; do not report as strong results.

---

## 3. Non-converged fluents — agent behavior + generated vs. expert

All five robustly-evaluable failures share one property: the rules *look* plausible but **diverge
behaviorally**, which is exactly what interval-level scoring is designed to catch.

### 3.1 `tuggingSpeed` — F1 0.52 (P=1.00, R=0.35): wrong criterion
**Behavior.** Precision 1.0, recall 0.35, `fp=0` → the generated rule is a **strict subset** of
gold.

```prolog
% EXPERT — fires for ANY vessel whose speed is in the fixed tugging band
initiatedAt(tuggingSpeed(Vessel)=true, T) :-
    happensAt(velocity(Vessel, Speed, _, _), T),
    thresholds(tuggingMin, TuggingMin), thresholds(tuggingMax, TuggingMax),
    inRange(Speed, TuggingMin, TuggingMax).

% GENERATED — used the per-vessel-type speed band, and restricted to vesselType
initiatedAt(tuggingSpeed(Vessel)=true, T) :-
    happensAt(velocity(...), T),
    vesselType(Vessel, Type), typeSpeed(Type, Min, Max, _),
    inRange(Speed, Min, Max).
```
The agent used `typeSpeed` (the per-type *moving* speed band, used by `movingSpeed`) instead of
the dedicated `thresholds(tuggingMin, tuggingMax)`, and added a `vesselType` restriction → narrower
condition ⊂ gold → misses 65% of intervals. **Notably, the agent defined `tuggingSpeed` correctly
in the standalone `tugging` run** — same fluent, different (wrong) guess depending on run context.

### 3.2 `movingSpeed` — F1 0.46 (per value: normal R=0.34, above R=0.18): wrong transition mechanics
**Behavior.** Each value has `fp=0` + low recall → subset per value.
The structure was right (`vesselType` + `typeSpeed`), but the agent added **explicit per-value
terminations** (e.g. `terminatedAt(movingSpeed=above) :- Speed =< Max`). The expert relies on
**multi-valued auto-termination** (initiating `=normal` ends `=above`) and only terminates *all*
values when speed drops below `movingMin`. The extra terminations fragment the intervals and
leave coverage gaps → recall collapses, precision stays perfect.

### 3.3 `trawlingMovement` — F1 0.70 (=true 0.87, =false **0.00**): missed an RTEC construct
**Behavior.** `=true` over-fires slightly (P=0.77, R=1.0); **`=false` scores 0.0**
(`tp=0, fp=0, fn=162162`) — nothing matched, dragging macro-F1 down.

```prolog
% EXPERT — =false is produced by a DEADLINE, not explicit events:
fi(trawlingMovement(V)=true, trawlingMovement(V)=false, TrawlingCrs) :-
    thresholds(trawlingCrs, TrawlingCrs).     % true -> false after a timeout

% GENERATED — tried to synthesize =false from explicit events (wrong mechanism):
initiatedAt(trawlingMovement(V)=false, T) :- happensAt(gap_start(V), T).
initiatedAt(trawlingMovement(V)=false, T) :- happensAt(leavesArea(V, Area), T), areaType(Area, fishing).
```
The agent had no knowledge of the **`fi/3` deadline construct**, so its `=false` intervals never
align with gold. This is not inferable from the NL — a genuine ceiling.

### 3.4 `loitering` — F1 0.44 (P=0.28, R=0.93): over-fires, complex interval algebra
**Behavior.** High recall, low precision → **over-firing** (`fp=1.67M`).

```prolog
% EXPERT — a long, exclusion-based SD definition:
holdsFor(loitering(Vessel)=true, I) :-
    holdsFor(lowSpeed(Vessel)=true, Il),
    holdsFor(stopped(Vessel)=farFromPorts, Is),
    union_all([Il, Is], Ils),
    holdsFor(withinArea(Vessel, nearCoast)=true, Inc),
    holdsFor(anchoredOrMoored(Vessel)=true, Iam),
    relative_complement_all(Ils, [Inc, Iam], Ii),   % EXCLUDE nearCoast & anchored
    thresholds(loiteringTime, LoiteringTime),
    intDurGreater(Ii, LoiteringTime, I).            % only if long enough
```
The over-firing (P=0.28) is consistent with the agent **omitting the `relative_complement_all`
exclusion** (loitering must *not* be near coast or anchored) and/or the `intDurGreater` duration
gate — so it asserts loitering far too broadly. Requires advanced interval-algebra constructs
(`relative_complement_all`, `union_all`, `intDurGreater`).

### 3.5 `drifting` — F1 0.30 (P=0.33, R=0.28): genuinely wrong (and a tooling bug, now fixed)
**Behavior.** Both `fp` and `fn` high → not a subset; the rule is wrong in both directions.
**Important context:** `drifting` originally **could not compile at all** — a false-positive in the
`compile_rules` arithmetic-binding check rejected the (correct) use of the background predicate
`absoluteAngleDiff/3`. That tooling bug was **fixed** (the check now recognizes any predicate call
as binding its arguments); in this run `drifting` compiles cleanly (5 successes, 0 failures) but
still only reaches 0.30. The residual error is a genuine synthesis difficulty: `drifting` depends
on the `absoluteAngleDiff` angle computation, the `TrueHeading = 511.0` "heading unavailable"
sentinel, and the `underWay` dependency — and the agent did not assemble all three correctly.

### 3.6 Low-confidence / not-evaluable
`sarMovement` (10), `trawling` (3), `inSAR` (1), plus the converged `sarSpeed` (3) / `pilotOps` (5)
have too few gold instances to score meaningfully on this window. Their numbers should be reported
as **indicative only**; a larger/targeted dataset is needed.

---

## 4. Failure taxonomy

| Category | Example | Nature | Fixable by |
|---|---|---|---|
| Wrong criterion | tuggingSpeed | used `typeSpeed` instead of `tuggingMin/Max` | richer vocabulary feedback |
| Wrong EC semantics | movingSpeed | broke multi-valued auto-termination | better RTEC guidance |
| Missing construct | trawlingMovement (`fi/3`), loitering (`relative_complement_all`), drifting | constructs not inferable from NL | surfacing constructs in syntax docs |
| Verifier false-positive | drifting (compile) | **harness bug blocked a correct rule** | **fixed** — tooling, not the model |

---

## 5. Observations

1. **Honest synthesis works, and is model-dependent.** With all leakage removed, kimi 2.7 reaches
   exact behavioral equivalence on 6/11 robustly-evaluable fluents — including an SD fluent — and
   the reasoning traces show it *inferring* rules from the domain, not copying.
2. **Behavioral (interval-level) verification is essential.** Every failure "looks like a valid
   rule" but diverges in output — wrong threshold, wrong value-transition, a missing deadline, an
   omitted exclusion. Visual rule similarity ≠ behavioral equivalence; this is the core
   justification for the CEGIS-against-gold design.
3. **A real ceiling exists for advanced constructs.** Fluents needing `fi/3` deadlines or
   `relative_complement_all`/`intDurGreater` interval algebra are not synthesizable from NL alone —
   the constructs must be surfaced to the model (future work).
4. **The harness itself was a bottleneck once.** `drifting` was blocked by a false-positive in the
   compile check, not by the model — found and fixed via this analysis. (Same investigation also
   fixed a no-tool-call termination hole and a gold-interval leak.)
5. **Evaluation validity is dataset-bound.** Rare activities (`tugging`, SAR, completed
   `trawling`) are absent or near-absent in the 54h window; full 21-fluent evaluation needs a
   larger or activity-targeted slice of `brest_critical.csv` (183 days available).
