:- dynamic vessel/1, vpair/2.

initiatedAt(withinArea(_110,_112)=true, _142, _80, _148) :-
     happensAtIE(entersArea(_110,_118),_80),_142=<_80,_80<_148,
     areaType(_118,_112).

initiatedAt(stopped(_110)=nearPorts, _150, _80, _156) :-
     happensAtIE(stop_start(_110),_80),_150=<_80,_80<_156,
     holdsAtProcessedSimpleFluent(_110,withinArea(_110,nearPorts)=true,_80).

initiatedAt(stopped(_110)=farFromPorts, _154, _80, _160) :-
     happensAtIE(stop_start(_110),_80),_154=<_80,_80<_160,
     \+holdsAtProcessedSimpleFluent(_110,withinArea(_110,nearPorts)=true,_80).

initiatedAt(lowSpeed(_110)=true, _126, _80, _132) :-
     happensAtIE(slow_motion_start(_110),_80),
     _126=<_80,
     _80<_132.

terminatedAt(withinArea(_110,_112)=true, _142, _80, _148) :-
     happensAtIE(leavesArea(_110,_118),_80),_142=<_80,_80<_148,
     areaType(_118,_112).

terminatedAt(withinArea(_110,_112)=true, _128, _80, _134) :-
     happensAtIE(gap_start(_110),_80),
     _128=<_80,
     _80<_134.

terminatedAt(stopped(_110)=_86, _126, _80, _132) :-
     happensAtIE(stop_end(_110),_80),
     _126=<_80,
     _80<_132.

terminatedAt(stopped(_110)=_86, _136, _80, _142) :-
     happensAtProcessedIE(_110,start(gap(_110)=_120),_80),
     _136=<_80,
     _80<_142.

terminatedAt(lowSpeed(_110)=true, _126, _80, _132) :-
     happensAtIE(slow_motion_end(_110),_80),
     _126=<_80,
     _80<_132.

terminatedAt(lowSpeed(_110)=true, _126, _80, _132) :-
     happensAtIE(gap_start(_110),_80),
     _126=<_80,
     _80<_132.

holdsForSDFluent(anchoredOrMoored(_110)=true,_80) :-
     holdsForProcessedSimpleFluent(_110,stopped(_110)=farFromPorts,_126),
     holdsForProcessedSimpleFluent(_110,withinArea(_110,anchorage)=true,_144),
     intersect_all([_126,_144],_162),
     holdsForProcessedSimpleFluent(_110,stopped(_110)=nearPorts,_178),
     union_all([_162,_178],_80).

holdsForSDFluent(loitering(_110)=true,_80) :-
     holdsForProcessedSimpleFluent(_110,lowSpeed(_110)=true,_126),
     holdsForProcessedSimpleFluent(_110,stopped(_110)=farFromPorts,_142),
     union_all([_126,_142],_160),
     holdsForProcessedSimpleFluent(_110,withinArea(_110,nearCoast)=true,_178),
     relative_complement_all(_160,[_178],_192),
     holdsForProcessedSDFluent(_110,anchoredOrMoored(_110)=true,_208),
     relative_complement_all(_192,[_208],_222),
     thresholds(loiteringTime,_228),
     intDurGreater(_222,_228,_80).

grounding(entersArea(_462,_464)) :- 
     vessel(_462),areaType(_464).

grounding(leavesArea(_462,_464)) :- 
     vessel(_462),areaType(_464).

grounding(gap_start(_462)) :- 
     vessel(_462).

grounding(withinArea(_468,_470)=true) :- 
     vessel(_468),areaType(_470).

grounding(stop_start(_462)) :- 
     vessel(_462).

grounding(stop_end(_462)) :- 
     vessel(_462).

grounding(stopped(_468)=_464) :- 
     vessel(_468),portStatus(_464).

grounding(slow_motion_start(_462)) :- 
     vessel(_462).

grounding(slow_motion_end(_462)) :- 
     vessel(_462).

grounding(lowSpeed(_468)=true) :- 
     vessel(_468).

grounding(anchoredOrMoored(_468)=true) :- 
     vessel(_468).

grounding(loitering(_468)=true) :- 
     vessel(_468).

needsGrounding(_386,_388,_390) :- 
     fail.

inputEntity(entersArea(_134,_136)).
inputEntity(stop_start(_134)).
inputEntity(slow_motion_start(_134)).
inputEntity(leavesArea(_134,_136)).
inputEntity(gap_start(_134)).
inputEntity(stop_end(_134)).
inputEntity(gap(_140)=_136).
inputEntity(slow_motion_end(_134)).

outputEntity(withinArea(_244,_246)=true).
outputEntity(stopped(_244)=nearPorts).
outputEntity(stopped(_244)=farFromPorts).
outputEntity(lowSpeed(_244)=true).
outputEntity(anchoredOrMoored(_244)=true).
outputEntity(loitering(_244)=true).

event(entersArea(_330,_332)).
event(stop_start(_330)).
event(slow_motion_start(_330)).
event(leavesArea(_330,_332)).
event(gap_start(_330)).
event(stop_end(_330)).
event(slow_motion_end(_330)).

simpleFluent(withinArea(_434,_436)=true).
simpleFluent(stopped(_434)=nearPorts).
simpleFluent(stopped(_434)=farFromPorts).
simpleFluent(lowSpeed(_434)=true).


sDFluent(anchoredOrMoored(_570)=true).
sDFluent(loitering(_570)=true).
sDFluent(gap(_570)=_566).

index(withinArea(_590,_650)=true,_590).
index(stopped(_590)=_644,_590).
index(lowSpeed(_590)=true,_590).
index(anchoredOrMoored(_590)=true,_590).
index(loitering(_590)=true,_590).
index(entersArea(_590,_644),_590).
index(stop_start(_590),_590).
index(slow_motion_start(_590),_590).
index(leavesArea(_590,_644),_590).
index(gap_start(_590),_590).
index(stop_end(_590),_590).
index(slow_motion_end(_590),_590).
index(gap(_590)=_644,_590).


cachingOrder2(_924, withinArea(_924,_926)=true) :- % level in dependency graph: 1, processing order in component: 1
     vessel(_924),areaType(_926).

cachingOrder2(_902, lowSpeed(_902)=true) :- % level in dependency graph: 1, processing order in component: 1
     vessel(_902).

cachingOrder2(_1162, stopped(_1162)=farFromPorts) :- % level in dependency graph: 2, processing order in component: 1
     vessel(_1162),portStatus(farFromPorts).

cachingOrder2(_1178, stopped(_1178)=nearPorts) :- % level in dependency graph: 2, processing order in component: 2
     vessel(_1178),portStatus(nearPorts).

cachingOrder2(_1408, anchoredOrMoored(_1408)=true) :- % level in dependency graph: 3, processing order in component: 1
     vessel(_1408).

cachingOrder2(_1548, loitering(_1548)=true) :- % level in dependency graph: 4, processing order in component: 1
     vessel(_1548).

collectGrounds([entersArea(_436,_450), stop_start(_436), slow_motion_start(_436), leavesArea(_436,_450), gap_start(_436), stop_end(_436), slow_motion_end(_436)],vessel(_436)).

collectGrounds([],vpair(_424,_426)).

dgrounded(withinArea(_706,_708)=true, vessel(_706)).
dgrounded(stopped(_664)=nearPorts, vessel(_664)).
dgrounded(stopped(_622)=farFromPorts, vessel(_622)).
dgrounded(lowSpeed(_590)=true, vessel(_590)).
dgrounded(anchoredOrMoored(_558)=true, vessel(_558)).
dgrounded(loitering(_526)=true, vessel(_526)).
