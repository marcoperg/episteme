:- module(episteme_relations, [
    relation_node/1,
    relation_origin/1,
    asserted_relation/5,
    immediate_relation/3,
    relation/3,
    outgoing/3,
    incoming/3
], [assertions, regtypes, modes, tabling, doccomments]).

:- doc(title, "Episteme Relation Queries").
:- doc(author, "Marco Pérez").
:- doc(module, "Queries the relation graph generated from Episteme Org files.

Authored assertions are stored once. Incoming navigation, declared inverses,
symmetric relations, subproperties, and transitive closure are derived views.
Generated facts remain disposable; Org is the authoritative representation.").

:- use_module('generated/relation_facts', [
    asserted/5,
    from_index/5,
    to_index/5
]).
:- use_module(relation_schema, [
    inverse_relation/2,
    symmetric_relation/1,
    transitive_relation/1,
    subproperty_relation/2
]).

% The generated module is validated before it is atomically replaced.
:- trust pred asserted(Id, Subject, Predicate, Object, Origin)
   => (atm(Id), relation_node(Subject), atm(Predicate),
       relation_node(Object), relation_origin(Origin)).
:- trust pred from_index(Subject, Predicate, Object, Id, Origin)
   => (relation_node(Subject), atm(Predicate), relation_node(Object),
       atm(Id), relation_origin(Origin)).
:- trust pred to_index(Object, Predicate, Subject, Id, Origin)
   => (relation_node(Object), atm(Predicate), relation_node(Subject),
       atm(Id), relation_origin(Origin)).

:- table immediate_relation/3.
:- table relation/3.

:- regtype relation_node/1 # "An addressable node in the relation graph.".

relation_node(note(Path)) :- atm(Path).
relation_node(source(Key)) :- atm(Key).

:- regtype relation_origin/1 # "The exact location of an authored assertion.".

relation_origin(org(Path, Line)) :-
    atm(Path),
    int(Line).

:- pred asserted_relation(Id, Subject, Predicate, Object, Origin)
   => (atm(Id), relation_node(Subject), atm(Predicate),
       relation_node(Object), relation_origin(Origin))
   # "Returns an authored assertion and its @var{Origin}.".

asserted_relation(Id, Subject, Predicate, Object, Origin) :-
    asserted(Id, Subject, Predicate, Object, Origin).

:- pred immediate_relation(Subject, Predicate, Object)
   => (relation_node(Subject), atm(Predicate), relation_node(Object))
   # "Returns a direct or schema-derived non-transitive relation.".

immediate_relation(Subject, Predicate, Object) :-
    from_index(Subject, Predicate, Object, _, _).
immediate_relation(Subject, Inverse, Object) :-
    to_index(Subject, Predicate, Object, _, _),
    inverse_pair(Predicate, Inverse).
immediate_relation(Subject, Predicate, Object) :-
    symmetric_relation(Predicate),
    to_index(Subject, Predicate, Object, _, _).
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
