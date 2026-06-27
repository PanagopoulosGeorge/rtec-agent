# RTEC Authoring Guide — Core (domain-agnostic)

This is the root context for an agent that writes RTEC (Run-Time Event Calculus) event
descriptions. It teaches the **language** and the **declarations that make a program
runnable**. Domain-specific signatures (events, input fluents, thresholds) live in the
per-domain files under `domains/`. The per-fluent task is supplied separately.

Sources: the RTEC teaching prompts (`resources/llms.docx`, RTEC-1..4, SF/SDF) and the
RTEC User Manual. The declaration layer (§4) and gotchas (§7) are NOT in the prompt set
but are mandatory — omitting them yields a program that compiles yet produces nothing.

---

## 1. Role

You are an assistant that constructs rules in the language of the Run-Time Event
Calculus (RTEC), given a composite-activity description in natural language. The Event
Calculus is a logic-based formalism for representing and reasoning about events and
their effects. RTEC is a Prolog implementation of the Event Calculus optimised for
composite-activity (complex-event) recognition over data streams.

## 2. Language conventions

Following Prolog convention, variables start with an upper-case letter, while predicates
and constants start with a lower-case letter. Each rule ends with a full stop “`.`”, and
the head of a rule is separated from its body with “`:-`”.

A **fluent** is a property that may have different values at different points in time.
The term `F=V` denotes that fluent `F` has value `V`. **Boolean** fluents are the special
case where the values are `true` and `false`.

Intervals are **right-open**: a term `(Ts,Te)` represents `[Ts, Te)`. A *list of maximal
intervals* is temporally sorted and contains disjoint intervals.

## 3. Predicates

| Predicate | Meaning |
|---|---|
| `happensAt(E,T)` | Event `E` occurs at time `T`. |
| `holdsAt(F=V,T)` | The value of fluent `F` is `V` at time `T`. |
| `holdsFor(F=V,I)` | `I` is the list of maximal intervals during which `F=V` holds continuously. |
| `initiatedAt(F=V,T)` | At `T`, a period during which `F=V` holds is initiated. |
| `terminatedAt(F=V,T)` | At `T`, a period during which `F=V` holds is terminated. |
| `union_all(L,I)` | `I` = union of the lists of maximal intervals in list `L`. |
| `intersect_all(L,I)` | `I` = intersection of the lists of maximal intervals in `L`. |
| `relative_complement_all(I',L,I)` | `I` = `I'` minus every list of maximal intervals in `L`. |

`not` expresses negation-by-failure. All head and body predicates of a simple-fluent
rule are evaluated at the **same** time-point `T`.

**Built-in events** (arity 1, argument is a fluent-value pair):
- `start(F=V)` — occurs at each starting point of a maximal interval of `F=V`.
- `end(F=V)` — occurs at each ending point of a maximal interval of `F=V`.

Interval-construct examples (from the manual):
```
union_all([[(5,20),(26,30)],[(28,35)]], [(5,20),(26,35)])
intersect_all([[(26,31)],[(21,26),(30,40)]], [(30,31)])
relative_complement_all([(5,20),(26,50)], [[(1,4),(18,22)],[(28,35)]], [(5,18),(26,28),(35,50)])
```

## 4. The two kinds of fluent definition

### 4a. Simple fluents — `initiatedAt` / `terminatedAt`
For a simple fluent `F`, `F=V` holds at `T` if it was initiated by an event before `T`
and not terminated in between (law of inertia). Schema:
```
initiatedAt(F=V, T) :-
    happensAt(E1, T) [, [not] happensAt(Ei, T) ..., [not] holdsAt(Fk=Vk, T) ...].
```
The first body literal is a positive `happensAt`; then a possibly-empty set of
positive/negative `happensAt`/`holdsAt` and background-knowledge predicates.
`terminatedAt` rules have the same shape. Use simple fluents when the activity is driven
by **events** that switch it on/off.

### 4b. Statically determined fluents — `holdsFor`
For a statically determined fluent `F`, the maximal intervals of `F=V` are computed from
the intervals of *other* fluents via interval constructs. Schema:
```
holdsFor(F=V, I) :-
    holdsFor(F1=V1, I1) [, holdsFor(Fn=Vn, In) ..., intervalConstruct(L, I) ...].
```
The first body literal is a `holdsFor` of a different FVP; then more `holdsFor`s and
interval constructs (`union_all`, `intersect_all`, `relative_complement_all`, `allen`).
The **last** interval construct binds the output `I`. Use SDFs to express “`F=V` holds
iff some Boolean combination of other fluents holds” — usually more concise and
efficient than the simple-fluent form.

## 5. MANDATORY declarations (not in the prompt set — do not skip)

A rule set without these compiles but recognises **nothing** (the compiler derives the
fluent processing order, `cachingOrder2/2`, from the groundings; no groundings ⇒ no
output ⇒ the run fails). For every event description you write, include:

- **`grounding/1` — required for every output fluent AND every input event you use:**
  ```
  grounding(<inputEvent>(Args))   :- <domain-object conditions>.
  grounding(<fluent>(Args)=Value) :- <domain-object conditions>.
  ```
- **`dynamicDomain/1`** — for entity domains discovered from the stream rather than
  declared up front:
  ```
  dynamicDomain(<entity>(_)).
  ```
- **`fi/3` + `p/1`** — delayed / future initiation (auto-termination after a deadline):
  ```
  fi(F=V1, F=V2, Delay).   % F=V2 is initiated Delay time-points after F=V1 is initiated
  p(F=V1).                 % a re-initiation of F=V1 postpones that future initiation
  ```
- **`index/2`** — optional retrieval optimisation: `index(<event or fluent=value>, Arg).`

## 6. Complete worked example (domain-agnostic toy)

A person is happy when rich or at a pub; winning the lottery makes you rich, losing your
wallet undoes it. This shows BOTH fluent kinds and the full declaration layer:

```prolog
% --- recognition logic ---
initiatedAt(rich(X)=true, T)  :- happensAt(win_lottery(X), T).      % simple fluent
terminatedAt(rich(X)=true, T) :- happensAt(lose_wallet(X), T).
initiatedAt(location(X)=Y, T) :- happensAt(go_to(X,Y), T).         % multi-valued simple fluent

holdsFor(happy(X)=true, I) :-                                       % statically determined
    holdsFor(rich(X)=true, I1),
    holdsFor(location(X)=pub, I2),
    union_all([I1,I2], I).

% --- declarations (MANDATORY) ---
grounding(win_lottery(Person))       :- person(Person).
grounding(lose_wallet(Person))       :- person(Person).
grounding(go_to(Person, Place))      :- person(Person), place(Place).
grounding(rich(Person)=true)         :- person(Person).
grounding(location(Person)=Place)    :- person(Person), place(Place).
grounding(happy(Person)=true)        :- person(Person).
```
(`person/1`, `place/1` are domain objects supplied as background knowledge; add
`dynamicDomain(person(_)).` if persons are to be discovered from the stream instead.)

## 7. Operational semantics & gotchas (hard-won)

- **The `+1` offset.** RTEC initiates a fluent at `T+1` when `initiatedAt(...,T)`. So a
  recognised interval’s endpoints are shifted `+1` relative to the event time-points that
  drove them. When sanity-checking recognised intervals against the stream, expect this
  shift — do not "fix" it.
- **Right-open intervals & window edges.** An interval still open at the end of a window
  is reported with an end time of `windowEnd+1` (or `inf`). Not a bug.
- **Self-contained vs derived dependencies.** You may terminate on a raw input event
  (e.g. `happensAt(gap_start(V),T)`) — self-contained — or on a built-in over another
  fluent (e.g. `happensAt(start(gap(V)=_),T)`) — which requires you to ALSO define that
  fluent. Prefer self-contained unless the activity genuinely needs the derived fluent.
- **Degenerate output = missing grounding.** If `rtec_compile` warns “0 output entities
  (no cachingOrder2)”, you omitted a `grounding/1`. Add groundings for every fluent and
  every input event before running.
- **Never guess names or thresholds.** Discover exact event names, argument arity, entity
  ids, and threshold values from the tools / the domain file — guessing silently fails.
- **Input data format** (for reference; you don’t write this, you read it):
  - input event: `EventType|ArrivalTime|OccurrTime|Attr1|...|AttrN`
  - input fluent at a time-point: `FluentType|ArrivalTime|OccurrTime|Value|Attr1|...`
  - input fluent over an interval: `FluentType|ArrivalTime|StartT|EndT|Value|Attr1|...`

## 8. Grammar (formal, condensed)

An event-description rule is one of: a simple-fluent rule (`initiatedAt`/`terminatedAt`),
an output statically-determined-fluent rule (`holdsFor`), an output-event rule
(`happensAt` with a body), an `fi/3` fact, a `p/1` fact, a `grounding/1` rule, an
`index/2` declaration, or a `dynamicDomain/1` declaration. Interval operations are
`union_all/2`, `intersect_all/2`, `relative_complement_all/3`, and `allen/5`
(`allen(Rel,S,T,OutMode,I)` with `Rel ∈ {before,meets,starts,finishes,during,overlaps,
equal}` and `OutMode ∈ {source,target,union,intersect,complement,complement_inv}`).
