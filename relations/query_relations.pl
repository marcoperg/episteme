#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_package([assertions]).

:- doc(title, "Episteme Relation Query CLI").
:- doc(author, "Marco Pérez").
:- doc(module, "Command-line adapter used by Emacs and repository tools.").

:- use_module(episteme_relations, [asserted_relation/5, citations_to/4]).
:- use_module(library(aggregates), [setof/3]).
:- use_module(library(format), [format/2]).

:- pred main(Args) : list(Args)
   # "Runs a relation query described by @var{Args}.".

main([references, Key]) :- !,
    print_reference_notes(Key).
main(_) :-
    format("usage: query-relations references CITEKEY~n", []),
    halt(2).

:- pred print_reference_notes(Key) : atm(Key)
   # "Prints predicate/path rows for notes referring to a citation key.".

print_reference_notes(Key) :-
    (   setof(Row,
              reference_row(Key, Row),
              Rows) ->
        print_rows(Rows)
    ;   true
    ).

:- pred reference_row(Key, Row) : atm(Key)
   # "Returns one authored relation or citation occurrence for @var{Key}.".

reference_row(Key, row(Path, Line, Column, cites, Locator)) :-
    citations_to(source(Key), note(Path), Locator, org(Path, Line, Column)).
reference_row(Key, row(Path, Line, 1, Predicate, no_locator)) :-
    asserted_relation(_, note(Path), Predicate, source(Key), org(Path, Line)),
    Predicate \== cites.

:- pred print_rows(Rows) : list(Rows)
   # "Prints occurrence rows as tab-separated values.".

print_rows([]).
print_rows([row(Path, Line, Column, Predicate, no_locator)|Rows]) :- !,
    format("~w\t~w\t~d\t~d\t~n", [Predicate, Path, Line, Column]),
    print_rows(Rows).
print_rows([row(Path, Line, Column, Predicate, locator(Locator))|Rows]) :-
    format("~w\t~w\t~d\t~d\t~w~n",
           [Predicate, Path, Line, Column, Locator]),
    print_rows(Rows).
