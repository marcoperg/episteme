#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_module('../relations/episteme_relations', [
    asserted_relation/5,
    citation_occurrence/5,
    citations_to/4,
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
    \+ relation(source(Key), informed_by, note(Path)),
    CitationKey = 'inestaOptimalEntanglementDistribution2023',
    CitationPath = 'GIICC/Preguntas QIA.org',
    citation_occurrence(_, note(CitationPath), source(CitationKey), no_locator,
                        org(CitationPath, 7, 17)),
    citations_to(source(CitationKey), note(CitationPath), no_locator,
                 org(CitationPath, 7, 17)).
