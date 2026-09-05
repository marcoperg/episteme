:- module(relation_schema, [
    inverse_relation/2,
    symmetric_relation/1,
    transitive_relation/1,
    subproperty_relation/2
], [assertions, nativeprops, doccomments]).

:- doc(title, "Episteme Relation Schema").
:- doc(author, "Marco Pérez").
:- doc(module, "Declares semantic properties of relation predicates.
Unknown predicates remain ordinary directed relations. Add properties only when
their semantics are justified by a repeated query or documented use case.").

:- pred inverse_relation(Predicate, Inverse)
   => (atm(Predicate), atm(Inverse))
   # "@var{Predicate} and @var{Inverse} denote converse relations.".

inverse_relation(informed_by, informs).
inverse_relation(cites, cited_by).
inverse_relation(primary_context, contains_note).
inverse_relation(parent_context, child_context).

:- pred symmetric_relation(Predicate)
   => atm(Predicate)
   # "@var{Predicate} has the same meaning in both directions.".

symmetric_relation(_) :- fail.

:- pred transitive_relation(Predicate)
   => atm(Predicate)
   # "@var{Predicate} admits transitive closure.".

transitive_relation(_) :- fail.

:- pred subproperty_relation(Predicate, SuperPredicate)
   => (atm(Predicate), atm(SuperPredicate))
   # "@var{Predicate} entails the more general @var{SuperPredicate}.".

subproperty_relation(_, _) :- fail.
