# RTEC Authoring Guide — Maritime Situational Awareness (MSA)

Domain signature for the `maritime` app. Use with `rtec_core.md`. The events, input
fluent, and background-knowledge predicates below are the EXACT signature from the RTEC
teaching prompts (`resources/llms.docx`). Discover concrete values (entity ids, threshold
numbers, speed distributions) with `inspect_stream('maritime', ...)` and
`inspect_background('maritime', <pattern>)`.

> Leakage note: the worked examples in §4 (`withinArea`, `stopped`, `underWay`,
> `rendezVous`) are *taught*. They must be excluded from any measured evaluation set.

---

## 1. Events (in addition to the RTEC built-ins `start`/`end`)

| Event | Meaning |
|---|---|
| `change_in_speed_start(Vessel)` | Vessel started changing its speed. |
| `change_in_speed_end(Vessel)` | Vessel stopped changing its speed. |
| `change_in_heading(Vessel)` | Vessel changed its heading. |
| `stop_start(Vessel)` | Vessel started being idle. |
| `stop_end(Vessel)` | Vessel stopped being idle. |
| `slow_motion_start(Vessel)` | Vessel started moving at a low speed. |
| `slow_motion_end(Vessel)` | Vessel stopped moving at a low speed. |
| `gap_start(Vessel)` | Vessel stopped sending position signals. |
| `gap_end(Vessel)` | Vessel resumed sending position signals. |
| `entersArea(Vessel, AreaID)` | Vessel enters an area with id `AreaID`. |
| `leavesArea(Vessel, AreaID)` | Vessel leaves an area with id `AreaID`. |
| `velocity(Vessel, Speed, CourseOverGround, TrueHeading)` | Vessel moves at `Speed`, heading-of-travel `CourseOverGround`, bow direction `TrueHeading`. |

Convention (not discoverable from names): `TrueHeading = 511.0` means **heading
unavailable** — exclude it when reasoning about heading (e.g. drifting).

## 2. Input fluent

| Input fluent | Meaning |
|---|---|
| `proximity(Vessel1, Vessel2) = true` | The two vessels are close to each other. **Arrives in the stream as intervals**, so it must be loaded with `collectIntervals` (see below). |

`proximity` is an INPUT fluent over vessel **pairs**. To use it, your program MUST declare:
```prolog
collectIntervals(proximity(_,_)=true).            % load the interval stream (else holdsFor returns [])
dynamicDomain(vpair(_Vessel1, _Vessel2)).         % the pair domain, discovered from input
grounding(proximity(Vessel1, Vessel2)=true) :- vpair(Vessel1, Vessel2).
```
Output fluents over vessel pairs (`tugging`, `rendezVous`, `pilotOps`) are grounded via
`vpair` too, e.g. `grounding(tugging(V1,V2)=true) :- vpair(V1, V2).` Without
`collectIntervals`, `holdsFor(proximity(...), I)` is empty and these fluents never fire.

## 3. Background-knowledge predicates

`thresholds(Type, Value)` — threshold values (usable in arithmetic/comparisons). Retrieve
exact numbers with `inspect_background('maritime','thresholds')`:

| Threshold type | Meaning |
|---|---|
| `hcNearCoastMax` | Max safe sailing speed in a coastal area. |
| `adriftAngThr` | Max heading-vs-bow angle difference for which a vessel is NOT drifting. |
| `aOrMTime` | Max idle time before a vessel is considered anchored/moored. |
| `trawlspeedMin` / `trawlspeedMax` | Speed bounds of a trawling vessel. |
| `tuggingMin` / `tuggingMax` | Speed bounds of a tugging operation. |
| `tuggingTime` | Min duration of a tugging operation. |
| `movingMin` / `movingMax` | Speed bounds of a moving vessel. |
| `sarMinSpeed` | Min speed of a SAR vessel. |
| `trawlingTime` | Min duration of a trawling activity. |
| `loiteringTime` | Min duration of a loitering activity. |

Other background predicates:
| Predicate | Meaning |
|---|---|
| `typeSpeed(Type, Min, Max, Avg)` | Min/max/avg speed per vessel type. |
| `vesselType(Vessel, Type)` | Vessel type of each vessel. |
| `oneIsTug(V1, V2)` / `oneIsPilot(V1, V2)` / `twoAreTugs(V1, V2)` | Crew/role helpers. |
| `intDurGreater(I, V, I2)` | Keep intervals of `I` longer than `V`. |
| `absoluteAngleDiff(A1, A2, C)` | Absolute angle difference. |

Domain objects for groundings: `vessel(V)` (entity, dynamic), `areaType(AreaType)`,
`portStatus(nearPorts|farFromPorts)`, `movingStatus(below|normal|above)`.

## 4. Worked examples (taught — exclude from evaluation)

### 4a. Simple fluent — `withinArea`
Starts when a vessel enters an area; ends when it leaves that area, or on a comms gap.
```prolog
initiatedAt(withinArea(Vessel, AreaType)=true, T) :-
    happensAt(entersArea(Vessel, Area), T),
    areaType(Area, AreaType).
terminatedAt(withinArea(Vessel, AreaType)=true, T) :-
    happensAt(leavesArea(Vessel, Area), T),
    areaType(Area, AreaType).
terminatedAt(withinArea(Vessel, _AreaType)=true, T) :-
    happensAt(gap_start(Vessel), T).
% declarations
dynamicDomain(vessel(_Vessel)).
grounding(entersArea(V,Area)) :- vessel(V), areaType(Area).
grounding(leavesArea(V,Area)) :- vessel(V), areaType(Area).
grounding(gap_start(V))       :- vessel(V).
grounding(withinArea(Vessel, AreaType)=true) :- vessel(Vessel), areaType(AreaType).
```

### 4b. Multi-valued simple fluent — `stopped`
Starts when a vessel is idle near a port (`nearPorts`) or far from all ports
(`farFromPorts`); ends when it moves again, or on a comms gap. Note the use of
`holdsAt(withinArea...)` for the location condition and the built-in `start(gap(...))`.
```prolog
initiatedAt(stopped(Vessel)=nearPorts, T) :-
    happensAt(stop_start(Vessel), T),
    holdsAt(withinArea(Vessel, nearPorts)=true, T).
initiatedAt(stopped(Vessel)=farFromPorts, T) :-
    happensAt(stop_start(Vessel), T),
    \+ holdsAt(withinArea(Vessel, nearPorts)=true, T).
terminatedAt(stopped(Vessel)=_Status, T) :-
    happensAt(stop_end(Vessel), T).
terminatedAt(stopped(Vessel)=_Status, T) :-
    happensAt(start(gap(Vessel)=_GapStatus), T).
% declarations
grounding(stop_start(V)) :- vessel(V).
grounding(stop_end(V))   :- vessel(V).
grounding(stopped(Vessel)=PortStatus) :- vessel(Vessel), portStatus(PortStatus).
```
(`stopped` references `withinArea` and the `gap` fluent — under whole-program synthesis
those must also be defined if used.)

### 4c. Statically determined fluent — `underWay`
Holds as long as a vessel is not stopped, expressed as the union of the `movingSpeed`
values.
```prolog
holdsFor(underWay(Vessel)=true, I) :-
    holdsFor(movingSpeed(Vessel)=below, I1),
    holdsFor(movingSpeed(Vessel)=normal, I2),
    holdsFor(movingSpeed(Vessel)=above, I3),
    union_all([I1,I2,I3], I).
grounding(underWay(Vessel)=true) :- vessel(Vessel).
```

### 4d. Statically determined fluent — `rendezVous`
Two vessels (neither a tug nor pilot) are close, both slow or stopped far from ports, and
not near a port/coast, for longer than a minimum duration. Shows `union_all`,
`intersect_all`, `relative_complement_all`, a threshold, and `intDurGreater`.
```prolog
holdsFor(rendezVous(Vessel1, Vessel2)=true, I) :-
    holdsFor(proximity(Vessel1, Vessel2)=true, Ip),
    \+ oneIsTug(Vessel1, Vessel2),
    \+ oneIsPilot(Vessel1, Vessel2),
    holdsFor(lowSpeed(Vessel1)=true, Il1),
    holdsFor(lowSpeed(Vessel2)=true, Il2),
    holdsFor(stopped(Vessel1)=farFromPorts, Is1),
    holdsFor(stopped(Vessel2)=farFromPorts, Is2),
    union_all([Il1, Is1], I1b),
    union_all([Il2, Is2], I2b),
    intersect_all([I1b, I2b, Ip], If), If\=[],
    holdsFor(withinArea(Vessel1, nearPorts)=true, Iw1),
    holdsFor(withinArea(Vessel2, nearPorts)=true, Iw2),
    holdsFor(withinArea(Vessel1, nearCoast)=true, Iw3),
    holdsFor(withinArea(Vessel2, nearCoast)=true, Iw4),
    relative_complement_all(If,[Iw1, Iw2, Iw3, Iw4], Ii),
    thresholds(rendezvousTime, RendezvousTime),
    intDurGreater(Ii, RendezvousTime, I).
grounding(rendezVous(Vessel1, Vessel2)=true) :- vpair(Vessel1, Vessel2).
```

## 5. Discovery pointers

- Event names / argument shapes / entity ids → `inspect_stream('maritime', event_type=…)`.
- Threshold numbers → `inspect_background('maritime','thresholds')`.
- Vessel/area types → `inspect_background('maritime','vesselType' | 'areaType' | 'typeSpeed')`.
- Helper predicates → `inspect_background('maritime','oneIsTug' | 'absoluteAngleDiff')`.
