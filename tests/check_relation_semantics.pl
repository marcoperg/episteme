#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_module('../relations/episteme_relations', [
    asserted_relation/5,
    relation/3,
    outgoing/3,
    incoming/3
]).

main(_) :-
    Path = 'arquitectura/Elementos constructivos/Bovedas.org',
    Key = 'muller&vogelMullerVogelAtlas1995',
    asserted_relation(_, note(Path), informed_by, source(Key), org(Path, _)),
    incoming(source(Key), informed_by, note(Path)),
    outgoing(source(Key), informs, note(Path)),
    relation(source(Key), informs, note(Path)),
    \+ relation(source(Key), informed_by, note(Path)).
