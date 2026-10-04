:- module(episteme_relations, [
    relation_node/1,
    note_node/1,
    source_node/1,
    context_node/1,
    repository_path/1,
    relation_origin/1,
    citation_locator/1,
    citation_origin/1,
    asserted_relation/5,
    citation_occurrence/5,
    citations_from/4,
    citations_to/4,
    note_path/2,
    primary_context/2,
    parent_context/2,
    inherited_relation/5,
    immediate_relation/3,
    relation/3,
    outgoing/3,
    incoming/3
], [assertions, regtypes, modes, tabling, doccomments]).

:- doc(title, "Episteme Relation Queries").
:- doc(author, "Marco Pérez").
:- doc(module, "Queries the relation graph generated from Episteme Org files.

Authored assertions are stored once, while citation occurrences retain locators
and exact positions. Notes use durable Org IDs; current paths and directory
contexts remain queryable structural facts. Incoming navigation, declared
inverses, symmetric relations, subproperties, and transitive closure are derived
views. Snapshot facts remain disposable; Org is the authoritative
representation.").

:- use_module('../org/org_snapshot', [
    asserted/5,
    from_index/5,
    asserted_citation/5,
    citation_from_index/5,
    citation_to_index/5,
    note_index/3,
    context_parent_index/2
]).
:- use_module('./relation_schema', [
    inverse_relation/2,
    symmetric_relation/1,
    transitive_relation/1,
    subproperty_relation/2,
    context_inheritable_relation/1
]).
:- use_module(library(pathnames), [path_basename/2]).

% The snapshot provider validates a complete replacement before installation.
:- trust pred asserted(Id, Subject, Predicate, Object, Origin)
   => (atm(Id), relation_node(Subject), atm(Predicate),
       relation_node(Object), relation_origin(Origin)).
:- trust pred from_index(Subject, Predicate, Object, Id, Origin)
   => (relation_node(Subject), atm(Predicate), relation_node(Object),
       atm(Id), relation_origin(Origin)).
:- trust pred asserted_citation(Id, Note, Source, Locator, Origin)
   => (atm(Id), note_node(Note), source_node(Source),
        citation_locator(Locator), citation_origin(Origin)).
:- trust pred citation_from_index(Note, Source, Locator, Id, Origin)
   => (note_node(Note), source_node(Source), citation_locator(Locator),
        atm(Id), citation_origin(Origin)).
:- trust pred citation_to_index(Source, Note, Locator, Id, Origin)
   => (source_node(Source), note_node(Note), citation_locator(Locator),
        atm(Id), citation_origin(Origin)).
:- trust pred note_index(Note, Path, Context)
   => (note_node(Note), repository_path(Path), context_node(Context)).
:- trust pred context_parent_index(Context, Parent)
   => (context_node(Context), context_node(Parent)).

:- table immediate_relation/3.
:- table relation/3.
:- table context_within/2.

:- regtype relation_node/1 # "An addressable node in the relation graph.".

relation_node(Note) :- note_node(Note).
relation_node(Source) :- source_node(Source).
relation_node(Context) :- context_node(Context).

:- regtype note_node/1 # "A note identified by a durable file-level Org ID.".

note_node(note(Id)) :- atm(Id).

:- regtype source_node/1 # "A bibliographic source identified by a citekey.".

source_node(source(Key)) :- atm(Key).

:- regtype context_node/1 # "A directory context in the Episteme tree.".

context_node(context(Path)) :- repository_path(Path).

:- regtype repository_path/1 # "A repository-relative file or directory path.".

repository_path(Path) :- atm(Path).

:- regtype relation_origin/1 # "The exact location of an authored assertion.".

relation_origin(org(Path, Line)) :-
    atm(Path),
    int(Line).

:- regtype citation_locator/1 # "A normalized Org citation locator, or @tt{no_locator}.".

citation_locator(no_locator).
citation_locator(locator(Value)) :- atm(Value).

:- regtype citation_origin/1 # "The exact location of a citation reference.".

citation_origin(org(Path, Line, Column)) :-
    atm(Path),
    int(Line),
    int(Column).

:- pred asserted_relation(Id, Subject, Predicate, Object, Origin)
   => (atm(Id), relation_node(Subject), atm(Predicate),
       relation_node(Object), relation_origin(Origin))
   # "Returns an authored assertion and its @var{Origin}.".

asserted_relation(Id, Subject, Predicate, Object, Origin) :-
    asserted(Id, Subject, Predicate, Object, Origin).

:- pred citation_occurrence(Id, Note, Source, Locator, Origin)
   => (atm(Id), note_node(Note), source_node(Source),
       citation_locator(Locator), citation_origin(Origin))
   # "Returns an authored citation reference with locator and exact origin.".

citation_occurrence(Id, Note, Source, Locator, Origin) :-
    asserted_citation(Id, Note, Source, Locator, Origin).

:- pred citations_from(+Note, Source, Locator, Origin)
   => (note_node(Note), source_node(Source), citation_locator(Locator),
       citation_origin(Origin))
   # "Enumerates citation occurrences authored in @var{Note}.".

citations_from(Note, Source, Locator, Origin) :-
    citation_from_index(Note, Source, Locator, _, Origin).

:- pred citations_to(+Source, Note, Locator, Origin)
   => (source_node(Source), note_node(Note), citation_locator(Locator),
       citation_origin(Origin))
   # "Enumerates citation occurrences referring to @var{Source}.".

citations_to(Source, Note, Locator, Origin) :-
    citation_to_index(Source, Note, Locator, _, Origin).

:- pred note_path(Note, Path)
   => (note_node(Note), repository_path(Path))
   # "Returns the current repository-relative path of an identified note.".

note_path(Note, Path) :-
    note_index(Note, Path, _).

:- pred primary_context(Note, Context)
   => (note_node(Note), context_node(Context))
   # "Returns the note's current directory classification.".

primary_context(Note, Context) :-
    note_index(Note, _, Context).

:- pred parent_context(Context, Parent)
   => (context_node(Context), context_node(Parent))
   # "Returns the direct parent of a repository context.".

parent_context(Context, Parent) :-
    context_parent_index(Context, Parent).

:- pred inherited_relation(Note, Predicate, Object, Scope, Origin)
   => (note_node(Note), atm(Predicate), relation_node(Object),
       context_node(Scope), relation_origin(Origin))
   # "Returns a context assertion inherited by an identified descendant note,
      retaining its declaring @var{Scope} and authored @var{Origin}.".

inherited_relation(Note, Predicate, Object, Scope, Origin) :-
    note_index(Note, Path, Context),
    path_basename(Path, Base),
    Base \== 'README.org',
    context_inheritable_relation(Predicate),
    from_index(Scope, Predicate, Object, _, Origin),
    Scope = context(_),
    context_within(Context, Scope).

:- pred context_within(Context, Ancestor)
   => (context_node(Context), context_node(Ancestor))
   # "Holds when a context equals or descends from @var{Ancestor}.".

context_within(Context, Context).
context_within(Context, Ancestor) :-
    parent_context(Context, Parent),
    context_within(Parent, Ancestor).

:- pred structural_relation(Subject, Predicate, Object)
   => (relation_node(Subject), atm(Predicate), relation_node(Object))
   # "Returns a relation derived from the current repository path tree.".

structural_relation(Note, primary_context, Context) :-
    primary_context(Note, Context).
structural_relation(Context, parent_context, Parent) :-
    parent_context(Context, Parent).

:- pred base_relation(Subject, Predicate, Object)
   => (relation_node(Subject), atm(Predicate), relation_node(Object))
   # "Returns an authored, structural, or context-inherited relation.".

base_relation(Subject, Predicate, Object) :-
    from_index(Subject, Predicate, Object, _, _).
base_relation(Subject, Predicate, Object) :-
    structural_relation(Subject, Predicate, Object).
base_relation(Note, Predicate, Object) :-
    inherited_relation(Note, Predicate, Object, _, _).

:- pred immediate_relation(Subject, Predicate, Object)
   => (relation_node(Subject), atm(Predicate), relation_node(Object))
   # "Returns a direct or schema-derived non-transitive relation.".

immediate_relation(Subject, Predicate, Object) :-
    base_relation(Subject, Predicate, Object).
immediate_relation(Subject, Inverse, Object) :-
    base_relation(Object, Predicate, Subject),
    inverse_pair(Predicate, Inverse).
immediate_relation(Subject, Predicate, Object) :-
    symmetric_relation(Predicate),
    base_relation(Object, Predicate, Subject).
immediate_relation(Subject, SuperPredicate, Object) :-
    immediate_relation(Subject, Predicate, Object),
    subproperty_relation(Predicate, SuperPredicate).

:- pred relation(Subject, Predicate, Object)
   => (relation_node(Subject), atm(Predicate), relation_node(Object))
   # "Returns an immediate relation or an explicitly enabled transitive consequence.".

relation(Subject, Predicate, Object) :-
    immediate_relation(Subject, Predicate, Object).
relation(Subject, Predicate, Object) :-
    transitive_relation(Predicate),
    relation(Subject, Predicate, Middle),
    immediate_relation(Middle, Predicate, Object).

:- pred outgoing(+Subject, Predicate, Object)
   => (relation_node(Subject), atm(Predicate), relation_node(Object))
   # "Enumerates relations leaving @var{Subject}.".

outgoing(Subject, Predicate, Object) :-
    relation(Subject, Predicate, Object).

:- pred incoming(+Object, Predicate, Subject)
   => (relation_node(Object), atm(Predicate), relation_node(Subject))
   # "Enumerates relations arriving at @var{Object} without changing their predicate.".

incoming(Object, Predicate, Subject) :-
    relation(Subject, Predicate, Object).

:- pred inverse_pair(Predicate, Inverse)
   => (atm(Predicate), atm(Inverse))
   # "Closes the declared inverse relation in both directions.".

inverse_pair(Predicate, Inverse) :-
    inverse_relation(Predicate, Inverse).
inverse_pair(Predicate, Inverse) :-
    inverse_relation(Inverse, Predicate).
