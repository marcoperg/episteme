#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_module('../ciao/relations/episteme_relations', [
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
:- use_module('../ciao/org/org_snapshot', [
    refresh_snapshot/1,
    snapshot_valid/0,
    snapshot_version/1
]).
:- use_module('../ciao/workflow/agent_todos', [
    agent_action_authority/2,
    completion_precondition/1
]).

main(_) :-
    refresh_snapshot('.'),
    snapshot_version(1),
    snapshot_valid,
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
                  org(CitationPath, 7, 17)),
    agent_action_authority(edit_note, autonomous),
    agent_action_authority(import_source, human_approval),
    completion_precondition(repository_validation_passes),
    catch((refresh_snapshot('/definitely/missing/episteme-root'),
           RefreshFailed = no),
          error(_, _),
          RefreshFailed = yes),
    RefreshFailed == yes,
    snapshot_valid,
    note_path(Note, Path).
