#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_module('../relations/episteme_relations', [
    asserted_relation/5,
    citation_occurrence/5,
    citations_to/4,
    note_path/2,
    primary_context/2,
    parent_context/2,
    relation/3,
    outgoing/3,
    incoming/3
]).

main(_) :-
    Path = 'arquitectura/Elementos constructivos/Bovedas.org',
    NoteId = 'DACCAFEB-EE88-4020-8575-53DDA65C7D92',
    Note = note(NoteId),
    Key = 'muller&vogelMullerVogelAtlas1995',
    asserted_relation(_, Note, informed_by, source(Key), org(Path, 7)),
    note_path(Note, Path),
    Context = context('arquitectura/Elementos constructivos'),
    ParentContext = context(arquitectura),
    primary_context(Note, Context),
    parent_context(Context, ParentContext),
    relation(Note, primary_context, Context),
    outgoing(Context, contains_note, Note),
    relation(Context, parent_context, ParentContext),
    relation(ParentContext, child_context, Context),
    incoming(source(Key), informed_by, Note),
    outgoing(source(Key), informs, Note),
    relation(source(Key), informs, Note),
    \+ relation(source(Key), informed_by, Note),
    CitationKey = 'inestaOptimalEntanglementDistribution2023',
    CitationPath = 'GIICC/Preguntas QIA.org',
    CitationNote = note('F500C926-7C1D-4163-A819-F75969D8D327'),
    citation_occurrence(_, CitationNote, source(CitationKey), no_locator,
                         org(CitationPath, 7, 17)),
    citations_to(source(CitationKey), CitationNote, no_locator,
                  org(CitationPath, 7, 17)).
