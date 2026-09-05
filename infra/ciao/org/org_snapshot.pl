:- module(org_snapshot, [
    refresh_snapshot/1,
    snapshot_valid/0,
    snapshot_issue/4,
    snapshot_version/1,
    asserted/5,
    from_index/5,
    to_index/5,
    asserted_citation/5,
    citation_from_index/5,
    citation_to_index/5,
    note_index/3,
    context_parent_index/2,
    agent_todo/5,
    agent_todo_citation/4
], [assertions, regtypes, modes, datafacts]).

:- doc(title, "Episteme Org Snapshot").
:- doc(author, "Episteme contributors").
:- doc(module, "Loads a validated, in-memory view of Episteme Org data.

The external Org parser emits schema-version-1 JSON. A refresh validates the
complete document before replacing the current @concept{snapshot}, so parser,
process, and schema failures leave the previous state available. Graph facts
are indexed in both directions; agent todos are retained even for files that
do not participate in the relation graph. Persistent multithreaded callers must
serialize refreshes with queries because table invalidation is process-wide.").

:- use_module(library(lists), [append/3, member/2, select/3]).
:- use_module(library(pathnames), [path_dirname/2]).
:- use_module(library(pillow/json), [string_to_json/2]).
:- use_module(library(process), [process_call/3]).
:- use_module(library(sort), [sort/2]).
:- use_module(library(tabling/tabling_rt), [abolish_all_tables/0]).

:- regtype snapshot_node/1.
snapshot_node(note(Id)) :- atm(Id).
snapshot_node(source(Key)) :- atm(Key).

:- regtype snapshot_note/1.
snapshot_note(note(Id)) :- atm(Id).

:- regtype snapshot_source/1.
snapshot_source(source(Key)) :- atm(Key).

:- regtype snapshot_context/1.
snapshot_context(context(Path)) :- atm(Path).

:- regtype snapshot_relation_origin/1.
snapshot_relation_origin(org(Path, Line)) :-
    atm(Path),
    int(Line).

:- regtype snapshot_citation_locator/1.
snapshot_citation_locator(no_locator).
snapshot_citation_locator(locator(Value)) :- atm(Value).

:- regtype snapshot_citation_origin/1.
snapshot_citation_origin(org(Path, Line, Column)) :-
    atm(Path),
    int(Line),
    int(Column).

:- regtype snapshot_note_ref/1.
snapshot_note_ref(note(Id)) :- atm(Id).
snapshot_note_ref(file(Path)) :- atm(Path).

:- regtype snapshot_todo_origin/1.
snapshot_todo_origin(org(Path, Start, End)) :-
    atm(Path),
    int(Start),
    int(End).

:- regtype snapshot_severity/1.
snapshot_severity('ERROR').
snapshot_severity('WARNING').
snapshot_severity('INFO').

:- data snapshot_state/1.

:- pred refresh_snapshot(+Root) : atm(Root)
   # "Runs the Org exporter below @var{Root}, validates its JSON, and
      atomically replaces the current in-memory snapshot.".

refresh_snapshot(Root) :-
    run_exporter(Root, JsonCodes),
    parse_snapshot(JsonCodes, Snapshot),
    set_fact(snapshot_state(Snapshot)),
    abolish_all_tables.

:- pred snapshot_valid
   # "Succeeds when the current snapshot contains no error issue.".

snapshot_valid :-
    snapshot_state(snapshot(_, valid, _, _, _, _, _, _, _)).

:- trust pred snapshot_issue(Severity, Path, Line, Message)
   => (snapshot_severity(Severity), atm(Path), int(Line), atm(Message))
   # "Enumerates a retained issue with @var{Severity}, @var{Path},
      @var{Line}, and @var{Message}.".

snapshot_issue(Severity, Path, Line, Message) :-
    snapshot_state(snapshot(_, _, Issues, _, _, _, _, _, _)),
    member(issue(Severity, Path, Line, Message), Issues).

:- trust pred snapshot_version(Version) => int(Version)
   # "Returns the installed JSON schema @var{Version}.".

snapshot_version(Version) :-
    snapshot_state(snapshot(Version, _, _, _, _, _, _, _, _)).

:- trust pred asserted(Id, Subject, Predicate, Object, Origin)
   => (atm(Id), snapshot_node(Subject), atm(Predicate),
       snapshot_node(Object), snapshot_relation_origin(Origin))
   # "Enumerates deduplicated assertion @var{Id} from @var{Subject} through
      @var{Predicate} to @var{Object} at @var{Origin}.".

asserted(Id, Subject, Predicate, Object, Origin) :-
    snapshot_state(snapshot(_, _, _, Relations, _, _, _, _, _)),
    member(relation(Id, Subject, Predicate, Object, Origin), Relations).

:- trust pred from_index(Subject, Predicate, Object, Id, Origin)
   => (snapshot_node(Subject), atm(Predicate), snapshot_node(Object),
       atm(Id), snapshot_relation_origin(Origin))
   # "Indexes assertion @var{Id} from @var{Subject} through @var{Predicate}
      to @var{Object} at @var{Origin}.".

from_index(Subject, Predicate, Object, Id, Origin) :-
    asserted(Id, Subject, Predicate, Object, Origin).

:- trust pred to_index(Object, Predicate, Subject, Id, Origin)
   => (snapshot_node(Object), atm(Predicate), snapshot_node(Subject),
       atm(Id), snapshot_relation_origin(Origin))
   # "Indexes assertion @var{Id} to @var{Object} through @var{Predicate}
      from @var{Subject} at @var{Origin}.".

to_index(Object, Predicate, Subject, Id, Origin) :-
    asserted(Id, Subject, Predicate, Object, Origin).

:- trust pred asserted_citation(Id, Note, Source, Locator, Origin)
   => (atm(Id), snapshot_note(Note), snapshot_source(Source),
       snapshot_citation_locator(Locator),
       snapshot_citation_origin(Origin))
   # "Enumerates citation @var{Id} from @var{Note} to @var{Source}, with
      @var{Locator} and exact @var{Origin}.".

asserted_citation(Id, Note, Source, Locator, Origin) :-
    snapshot_state(snapshot(_, _, _, _, Citations, _, _, _, _)),
    member(citation(Id, Note, Source, Locator, Origin), Citations).

:- trust pred citation_from_index(Note, Source, Locator, Id, Origin)
   => (snapshot_note(Note), snapshot_source(Source),
       snapshot_citation_locator(Locator), atm(Id),
       snapshot_citation_origin(Origin))
   # "Indexes citation @var{Id} from @var{Note} to @var{Source}, with
      @var{Locator} and exact @var{Origin}.".

citation_from_index(Note, Source, Locator, Id, Origin) :-
    asserted_citation(Id, Note, Source, Locator, Origin).

:- trust pred citation_to_index(Source, Note, Locator, Id, Origin)
   => (snapshot_source(Source), snapshot_note(Note),
       snapshot_citation_locator(Locator), atm(Id),
       snapshot_citation_origin(Origin))
   # "Indexes citation @var{Id} to @var{Source} from @var{Note}, with
      @var{Locator} and exact @var{Origin}.".

citation_to_index(Source, Note, Locator, Id, Origin) :-
    asserted_citation(Id, Note, Source, Locator, Origin).

:- trust pred note_index(Note, Path, Context)
   => (snapshot_note(Note), atm(Path), snapshot_context(Context))
   # "Enumerates graph-participating @var{Note} values, their @var{Path},
      and primary @var{Context}.".

note_index(Note, Path, Context) :-
    snapshot_state(snapshot(_, _, _, _, _, Notes, _, _, _)),
    member(note_entry(Note, Path, Context), Notes).

:- trust pred context_parent_index(Context, Parent)
   => (snapshot_context(Context), snapshot_context(Parent))
   # "Enumerates direct @var{Context}-to-@var{Parent} edges derived from
      indexed note contexts.".

context_parent_index(Context, Parent) :-
    snapshot_state(snapshot(_, _, _, _, _, _, Contexts, _, _)),
    member(context_edge(Context, Parent), Contexts).

:- trust pred agent_todo(Fingerprint, NoteRef, HeadingPath, Body, Origin)
   => (atm(Fingerprint), snapshot_note_ref(NoteRef),
       list(atm, HeadingPath), atm(Body), snapshot_todo_origin(Origin))
   # "Enumerates an agent todo identified by @var{Fingerprint}, retaining
      @var{NoteRef}, @var{HeadingPath}, @var{Body}, and @var{Origin}.".

agent_todo(Fingerprint, NoteRef, HeadingPath, Body, Origin) :-
    snapshot_state(snapshot(_, _, _, _, _, _, _, Todos, _)),
    member(todo_entry(Fingerprint, NoteRef, HeadingPath, Body, Origin), Todos).

:- trust pred agent_todo_citation(Fingerprint, Source, Locator, Origin)
   => (atm(Fingerprint), snapshot_source(Source),
       snapshot_citation_locator(Locator),
       snapshot_citation_origin(Origin))
   # "Enumerates a @var{Source}, @var{Locator}, and @var{Origin} citation
      hint contained in todo @var{Fingerprint}.".

agent_todo_citation(Fingerprint, Source, Locator, Origin) :-
    snapshot_state(snapshot(_, _, _, _, _, _, _, _, TodoCitations)),
    member(todo_citation(Fingerprint, Source, Locator, Origin),
           TodoCitations).

% ---------------------------------------------------------------------------

run_exporter(Root, JsonCodes) :-
    process_call('infra/bin/export-org-snapshot',
                 ['--root', '.'],
                 [cwd(Root), stdout(string(JsonCodes)),
                  stderr(string(ErrorCodes)), status(Status)]),
    accept_exporter_status(Status, ErrorCodes).

accept_exporter_status(0, _) :- !.
accept_exporter_status(1, _) :- !.
accept_exporter_status(Status, ErrorCodes) :-
    atom_codes(Error, ErrorCodes),
    throw(error(org_snapshot_exporter_failed(Status, Error),
                refresh_snapshot/1)).

parse_snapshot(JsonCodes, Snapshot) :-
    (   string_to_json(JsonCodes, Json) ->
        json_snapshot(Json, Snapshot)
    ;   invalid_snapshot(malformed_json)
    ).

json_snapshot(Json, Snapshot) :-
    object_values(Json, [schema_version, documents, issues],
                  [VersionJson, DocumentsJson, IssuesJson], root),
    expect_schema_version(VersionJson, Version),
    parse_documents(DocumentsJson, Documents),
    parse_issues(IssuesJson, Issues),
    collect_documents(Documents, Relations0, Citations0, Notes0,
                      Todos0, TodoCitations0),
    deduplicate_relations(Relations0, Relations),
    deduplicate_citations(Citations0, Citations),
    sort(Notes0, Notes),
    context_edges(Notes, Contexts0),
    sort(Contexts0, Contexts),
    sort(Todos0, Todos),
    sort(TodoCitations0, TodoCitations),
    issue_validity(Issues, Validity),
    Snapshot = snapshot(Version, Validity, Issues, Relations, Citations,
                        Notes, Contexts, Todos, TodoCitations).

expect_schema_version(Value, Version) :-
    expect_integer(Value, Version, schema_version),
    (   Version == 1 ->
        true
    ;   invalid_snapshot(unknown_schema_version(Version))
    ).

parse_documents([], []) :- !.
parse_documents([Json|Jsons], [Document|Documents]) :- !,
    parse_document(Json, Document),
    parse_documents(Jsons, Documents).
parse_documents(Value, _) :-
    invalid_snapshot(expected_array(documents, Value)).

parse_document(Json, Document) :-
    object_values(Json,
                  [citations, context, file_id, path, relations, todos],
                  [CitationsJson, ContextJson, FileIdJson, PathJson,
                   RelationsJson, TodosJson], document),
    expect_atom(ContextJson, Context, field(document, context)),
    expect_nullable_atom(FileIdJson, FileId, field(document, file_id)),
    expect_atom(PathJson, Path, field(document, path)),
    parse_relations(RelationsJson, Relations),
    parse_citations(CitationsJson, Citations),
    parse_todos(TodosJson, Path, Todos),
    validate_graph_ids(FileId, Relations, Citations),
    Document = document(FileId, Path, Context, Relations, Citations, Todos).

parse_relations([], []) :- !.
parse_relations([Json|Jsons], [Relation|Relations]) :- !,
    parse_relation(Json, Relation),
    parse_relations(Jsons, Relations).
parse_relations(Value, _) :-
    invalid_snapshot(expected_array(relations, Value)).

parse_relation(Json, relation(Id, Line, Predicate, Target)) :-
    object_values(Json, [id, line, predicate, target, target_kind],
                  [IdJson, LineJson, PredicateJson, TargetJson,
                   TargetKindJson], relation),
    expect_nullable_atom(IdJson, Id, field(relation, id)),
    expect_integer(LineJson, Line, field(relation, line)),
    expect_atom(PredicateJson, Predicate, field(relation, predicate)),
    expect_atom(TargetJson, Target, field(relation, target)),
    expect_atom(TargetKindJson, TargetKind, field(relation, target_kind)),
    (   TargetKind == source ->
        true
    ;   invalid_snapshot(unknown_target_kind(TargetKind))
    ).

parse_citations([], []) :- !.
parse_citations([Json|Jsons], [Citation|Citations]) :- !,
    parse_citation(Json, Citation),
    parse_citations(Jsons, Citations).
parse_citations(Value, _) :-
    invalid_snapshot(expected_array(citations, Value)).

parse_citation(Json,
               citation_record(Id, RelationId, Line, Column, Key, Locator)) :-
    object_values(Json,
                  [column, id, key, line, locator, relation_id],
                  [ColumnJson, IdJson, KeyJson, LineJson, LocatorJson,
                   RelationIdJson], citation),
    expect_integer(ColumnJson, Column, field(citation, column)),
    expect_nullable_atom(IdJson, Id, field(citation, id)),
    expect_atom(KeyJson, Key, field(citation, key)),
    expect_integer(LineJson, Line, field(citation, line)),
    expect_locator(LocatorJson, Locator, field(citation, locator)),
    expect_nullable_atom(RelationIdJson, RelationId,
                         field(citation, relation_id)).

parse_todos([], _, []) :- !.
parse_todos([Json|Jsons], DocumentPath, [Todo|Todos]) :- !,
    parse_todo(Json, DocumentPath, Todo),
    parse_todos(Jsons, DocumentPath, Todos).
parse_todos(Value, _, _) :-
    invalid_snapshot(expected_array(todos, Value)).

parse_todo(Json, DocumentPath,
           todo_record(Fingerprint, HeadingPath, Body, Start, End, Hints)) :-
    object_values(Json,
                  [body, citation_hints, end_line, fingerprint,
                   heading_path, path, start_line],
                  [BodyJson, HintsJson, EndJson, FingerprintJson,
                   HeadingPathJson, PathJson, StartJson], todo),
    expect_atom(BodyJson, Body, field(todo, body)),
    parse_citation_hints(HintsJson, Hints),
    expect_integer(EndJson, End, field(todo, end_line)),
    expect_atom(FingerprintJson, Fingerprint, field(todo, fingerprint)),
    parse_atom_array(HeadingPathJson, HeadingPath,
                     field(todo, heading_path)),
    expect_atom(PathJson, Path, field(todo, path)),
    expect_integer(StartJson, Start, field(todo, start_line)),
    (   Path == DocumentPath ->
        true
    ;   invalid_snapshot(todo_path_mismatch(DocumentPath, Path))
    ).

parse_citation_hints([], []) :- !.
parse_citation_hints([Json|Jsons], [Hint|Hints]) :- !,
    parse_citation_hint(Json, Hint),
    parse_citation_hints(Jsons, Hints).
parse_citation_hints(Value, _) :-
    invalid_snapshot(expected_array(citation_hints, Value)).

parse_citation_hint(Json, hint(Line, Column, Key, Locator)) :-
    object_values(Json, [column, key, line, locator],
                  [ColumnJson, KeyJson, LineJson, LocatorJson],
                  citation_hint),
    expect_integer(ColumnJson, Column, field(citation_hint, column)),
    expect_atom(KeyJson, Key, field(citation_hint, key)),
    expect_integer(LineJson, Line, field(citation_hint, line)),
    expect_locator(LocatorJson, Locator, field(citation_hint, locator)).

parse_issues([], []) :- !.
parse_issues([Json|Jsons], [Issue|Issues]) :- !,
    parse_issue(Json, Issue),
    parse_issues(Jsons, Issues).
parse_issues(Value, _) :-
    invalid_snapshot(expected_array(issues, Value)).

parse_issue(Json, issue(Severity, Path, Line, Message)) :-
    object_values(Json, [line, message, path, severity],
                  [LineJson, MessageJson, PathJson, SeverityJson], issue),
    expect_integer(LineJson, Line, field(issue, line)),
    expect_atom(MessageJson, Message, field(issue, message)),
    expect_atom(PathJson, Path, field(issue, path)),
    expect_atom(SeverityJson, Severity, field(issue, severity)),
    expect_severity(Severity).

parse_atom_array([], [], _) :- !.
parse_atom_array([Json|Jsons], [Atom|Atoms], Field) :- !,
    expect_atom(Json, Atom, Field),
    parse_atom_array(Jsons, Atoms, Field).
parse_atom_array(Value, _, Field) :-
    invalid_snapshot(expected_array(Field, Value)).

object_values(json(Attrs), Fields, Values, Where) :- !,
    take_fields(Fields, Attrs, Values, Rest, Where),
    (   Rest == [] ->
        true
    ;   invalid_snapshot(unexpected_fields(Where, Rest))
    ).
object_values(Value, _, _, Where) :-
    invalid_snapshot(expected_object(Where, Value)).

take_fields([], Attrs, [], Attrs, _).
take_fields([Field|Fields], Attrs0, [Value|Values], Attrs, Where) :-
    (   select(Field=Value, Attrs0, Attrs1) ->
        take_fields(Fields, Attrs1, Values, Attrs, Where)
    ;   invalid_snapshot(missing_field(Where, Field))
    ).

expect_atom(string(Codes), Atom, _) :- !,
    atom_codes(Atom, Codes).
expect_atom(Value, _, Field) :-
    invalid_snapshot(expected_string(Field, Value)).

expect_nullable_atom(null, none, _) :- !.
expect_nullable_atom(string(Codes), some(Atom), _) :- !,
    atom_codes(Atom, Codes).
expect_nullable_atom(Value, _, Field) :-
    invalid_snapshot(expected_nullable_string(Field, Value)).

expect_integer(Value, Value, _) :- integer(Value), !.
expect_integer(Value, _, Field) :-
    invalid_snapshot(expected_integer(Field, Value)).

expect_locator(null, no_locator, _) :- !.
expect_locator(string(Codes), locator(Locator), _) :- !,
    atom_codes(Locator, Codes).
expect_locator(Value, _, Field) :-
    invalid_snapshot(expected_nullable_string(Field, Value)).

expect_severity('ERROR') :- !.
expect_severity('WARNING') :- !.
expect_severity('INFO') :- !.
expect_severity(Severity) :-
    invalid_snapshot(unknown_issue_severity(Severity)).

validate_graph_ids(none, Relations, Citations) :- !,
    require_absent_relation_ids(Relations),
    require_absent_citation_ids(Citations).
validate_graph_ids(some(_), Relations, Citations) :-
    require_relation_ids(Relations),
    require_citation_ids(Citations).

require_absent_relation_ids([]).
require_absent_relation_ids([relation(none, _, _, _)|Relations]) :-
    require_absent_relation_ids(Relations).
require_absent_relation_ids([relation(Id, _, _, _)|_]) :-
    invalid_snapshot(unexpected_relation_id(Id)).

require_relation_ids([]).
require_relation_ids([relation(some(_), _, _, _)|Relations]) :-
    require_relation_ids(Relations).
require_relation_ids([relation(none, _, _, _)|_]) :-
    invalid_snapshot(missing_graph_relation_id).

require_absent_citation_ids([]).
require_absent_citation_ids([
        citation_record(none, none, _, _, _, _)|Citations]) :-
    require_absent_citation_ids(Citations).
require_absent_citation_ids([Citation|_]) :-
    invalid_snapshot(unexpected_citation_id(Citation)).

require_citation_ids([]).
require_citation_ids([
        citation_record(some(_), some(_), _, _, _, _)|Citations]) :-
    require_citation_ids(Citations).
require_citation_ids([Citation|_]) :-
    invalid_snapshot(missing_graph_citation_id(Citation)).

% ---------------------------------------------------------------------------

collect_documents([], [], [], [], [], []).
collect_documents([Document|Documents], Relations, Citations, Notes,
                  Todos, TodoCitations) :-
    collect_document(Document, Relations0, Citations0, Notes0,
                     Todos0, TodoCitations0),
    collect_documents(Documents, Relations1, Citations1, Notes1,
                      Todos1, TodoCitations1),
    append(Relations0, Relations1, Relations),
    append(Citations0, Citations1, Citations),
    append(Notes0, Notes1, Notes),
    append(Todos0, Todos1, Todos),
    append(TodoCitations0, TodoCitations1, TodoCitations).

collect_document(document(FileId, Path, Context, RelationRecords,
                          CitationRecords, TodoRecords),
                 Relations, Citations, Notes, Todos, TodoCitations) :-
    collect_graph(FileId, Path, Context, RelationRecords, CitationRecords,
                  Relations, Citations, Notes),
    note_reference(FileId, Path, NoteRef),
    collect_todos(TodoRecords, NoteRef, Path, Todos, TodoCitations).

collect_graph(none, _, _, _, _, [], [], []) :- !.
collect_graph(some(_), _, _, [], [], [], [], []) :- !.
collect_graph(some(NoteId), Path, Context, RelationRecords, CitationRecords,
              Relations, Citations,
              [note_entry(note(NoteId), Path, context(Context))]) :-
    relation_facts(RelationRecords, NoteId, Path, AuthoredRelations),
    citation_facts(CitationRecords, NoteId, Path, CitationRelations,
                   Citations),
    append(AuthoredRelations, CitationRelations, Relations).

relation_facts([], _, _, []).
relation_facts([relation(some(Id), Line, Predicate, Target)|Records],
               NoteId, Path,
               [relation(Id, note(NoteId), Predicate, source(Target),
                         org(Path, Line))|Relations]) :-
    relation_facts(Records, NoteId, Path, Relations).

citation_facts([], _, _, [], []).
citation_facts([
        citation_record(some(Id), some(RelationId), Line, Column,
                        Key, Locator)|Records], NoteId, Path,
        [relation(RelationId, note(NoteId), cites, source(Key),
                  org(Path, Line))|Relations],
        [citation(Id, note(NoteId), source(Key), Locator,
                  org(Path, Line, Column))|Citations]) :-
    citation_facts(Records, NoteId, Path, Relations, Citations).

note_reference(none, Path, file(Path)) :- !.
note_reference(some(Id), _, note(Id)).

collect_todos([], _, _, [], []).
collect_todos([
        todo_record(Fingerprint, HeadingPath, Body, Start, End, Hints)|Records],
        NoteRef, Path,
        [todo_entry(Fingerprint, NoteRef, HeadingPath, Body,
                    org(Path, Start, End))|Todos], TodoCitations) :-
    todo_citations(Hints, Fingerprint, Path, HintCitations),
    collect_todos(Records, NoteRef, Path, Todos, RestCitations),
    append(HintCitations, RestCitations, TodoCitations).

todo_citations([], _, _, []).
todo_citations([hint(Line, Column, Key, Locator)|Hints], Fingerprint, Path,
               [todo_citation(Fingerprint, source(Key), Locator,
                              org(Path, Line, Column))|Citations]) :-
    todo_citations(Hints, Fingerprint, Path, Citations).

deduplicate_relations(Relations0, Relations) :-
    relation_keys(Relations0, Keyed0),
    sort(Keyed0, Keyed),
    collapse_relations(Keyed, Relations).

relation_keys([], []).
relation_keys([Relation|Relations],
              [keyed(Key, Relation)|KeyedRelations]) :-
    Relation = relation(_, Note, Predicate, Source, Origin),
    Key = relation_key(Note, Predicate, Source, Origin),
    relation_keys(Relations, KeyedRelations).

collapse_relations([], []).
collapse_relations([keyed(Key, Relation)|Keyed],
                   [Relation|Relations]) :-
    skip_relation_key(Key, Relation, Keyed, Rest),
    collapse_relations(Rest, Relations).

skip_relation_key(Key, Relation, [keyed(Key0, Relation0)|Keyed], Rest) :-
    Key == Key0, !,
    same_relation_id(Relation, Relation0),
    skip_relation_key(Key, Relation, Keyed, Rest).
skip_relation_key(_, _, Rest, Rest).

same_relation_id(relation(Id, _, _, _, _), relation(Id0, _, _, _, _)) :-
    (   Id == Id0 ->
        true
    ;   invalid_snapshot(conflicting_relation_ids(Id, Id0))
    ).

deduplicate_citations(Citations0, Citations) :-
    citation_keys(Citations0, Keyed0),
    sort(Keyed0, Keyed),
    collapse_citations(Keyed, Citations).

citation_keys([], []).
citation_keys([Citation|Citations],
              [keyed(Key, Citation)|KeyedCitations]) :-
    Citation = citation(_, Note, Source, Locator, Origin),
    Key = citation_key(Note, Source, Locator, Origin),
    citation_keys(Citations, KeyedCitations).

collapse_citations([], []).
collapse_citations([keyed(Key, Citation)|Keyed],
                   [Citation|Citations]) :-
    skip_citation_key(Key, Citation, Keyed, Rest),
    collapse_citations(Rest, Citations).

skip_citation_key(Key, Citation, [keyed(Key0, Citation0)|Keyed], Rest) :-
    Key == Key0, !,
    same_citation_id(Citation, Citation0),
    skip_citation_key(Key, Citation, Keyed, Rest).
skip_citation_key(_, _, Rest, Rest).

same_citation_id(citation(Id, _, _, _, _), citation(Id0, _, _, _, _)) :-
    (   Id == Id0 ->
        true
    ;   invalid_snapshot(conflicting_citation_ids(Id, Id0))
    ).

context_edges([], []).
context_edges([note_entry(_, _, context(Context))|Notes], Edges) :-
    context_chain(Context, ContextEdges),
    context_edges(Notes, RestEdges),
    append(ContextEdges, RestEdges, Edges).

context_chain('.', []) :- !.
context_chain(Context, [context_edge(context(Context), context(Parent))|Edges]) :-
    path_dirname(Context, Directory),
    parent_context_name(Directory, Parent),
    context_chain(Parent, Edges).

parent_context_name('', '.') :- !.
parent_context_name(Directory, Directory).

issue_validity(Issues, invalid) :-
    member(issue('ERROR', _, _, _), Issues), !.
issue_validity(_, valid).

invalid_snapshot(Reason) :-
    throw(error(invalid_org_snapshot(Reason), refresh_snapshot/1)).
