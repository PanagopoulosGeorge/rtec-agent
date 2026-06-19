collectIntervals(proximity(_,_)=true).
dynamicDomain(vessel(_Vessel)).
dynamicDomain(vpair(_Vessel1,_Vessel2)).
needsGrounding(_, _, _) :- fail.
buildFromPoints(_) :- fail.

% ── withinArea ──
initiatedAt(withinArea(Vessel, AreaType)=true, T) :-
    happensAt(entersArea(Vessel, Area), T),
    areaType(Area, AreaType).

terminatedAt(withinArea(Vessel, AreaType)=true, T) :-
    happensAt(leavesArea(Vessel, Area), T),
    areaType(Area, AreaType).

terminatedAt(withinArea(Vessel, _AreaType)=true, T) :-
    happensAt(gap_start(Vessel), T).

grounding(entersArea(V, Area)) :- vessel(V), areaType(Area).
grounding(leavesArea(V, Area)) :- vessel(V), areaType(Area).
grounding(gap_start(V)) :- vessel(V).
grounding(withinArea(V, AreaType)=true) :- vessel(V), areaType(AreaType).
index(withinArea(V, AreaType)=true, V).

% ── stopped ──
initiatedAt(stopped(Vessel)=nearPorts, T) :-
    happensAt(stop_start(Vessel), T),
    holdsAt(withinArea(Vessel, nearPorts)=true, T).

initiatedAt(stopped(Vessel)=farFromPorts, T) :-
    happensAt(stop_start(Vessel), T),
    \+holdsAt(withinArea(Vessel, nearPorts)=true, T).

terminatedAt(stopped(Vessel)=_Status, T) :-
    happensAt(stop_end(Vessel), T).

terminatedAt(stopped(Vessel)=_Status, T) :-
    happensAt(start(gap(Vessel)=_GapStatus), T).

grounding(stop_start(V)) :- vessel(V).
grounding(stop_end(V)) :- vessel(V).
grounding(stopped(V)=PortStatus) :- vessel(V), portStatus(PortStatus).
index(stopped(V)=_, V).

% ── lowSpeed ──
initiatedAt(lowSpeed(Vessel)=true, T) :-
    happensAt(slow_motion_start(Vessel), T).

terminatedAt(lowSpeed(Vessel)=true, T) :-
    happensAt(slow_motion_end(Vessel), T).

terminatedAt(lowSpeed(Vessel)=true, T) :-
    happensAt(gap_start(Vessel), T).

grounding(slow_motion_start(V)) :- vessel(V).
grounding(slow_motion_end(V)) :- vessel(V).
grounding(lowSpeed(V)=true) :- vessel(V).
index(lowSpeed(V)=true, V).

% ── anchoredOrMoored ──
holdsFor(anchoredOrMoored(Vessel)=true, I) :-
    holdsFor(stopped(Vessel)=farFromPorts, Isf),
    holdsFor(withinArea(Vessel, anchorage)=true, Ianch),
    intersect_all([Isf, Ianch], I1),
    holdsFor(stopped(Vessel)=nearPorts, Isn),
    union_all([I1, Isn], I).

grounding(anchoredOrMoored(V)=true) :- vessel(V).
index(anchoredOrMoored(V)=true, V).

% ── loitering ──
holdsFor(loitering(Vessel)=true, I) :-
    holdsFor(lowSpeed(Vessel)=true, Il),
    holdsFor(stopped(Vessel)=farFromPorts, Is),
    union_all([Il, Is], Ibase),
    holdsFor(withinArea(Vessel, nearCoast)=true, Ic),
    relative_complement_all(Ibase, [Ic], I1),
    holdsFor(anchoredOrMoored(Vessel)=true, Iam),
    relative_complement_all(I1, [Iam], I2),
    thresholds(loiteringTime, LoiteringTime),
    intDurGreater(I2, LoiteringTime, I).

grounding(loitering(V)=true) :- vessel(V).
index(loitering(V)=true, V).
