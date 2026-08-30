#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_package([assertions]).

:- doc(title, "Episteme Relation Query CLI").
:- doc(author, "Marco Pérez").
:- doc(module, "Command-line adapter used by Emacs and repository tools.").

:- use_module(episteme_relations, [asserted_relation/5]).
:- use_module(library(aggregates), [setof/3, (^)/2]).
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
    (   setof(Path-Line-Predicate,
              Id^asserted_relation(Id, note(Path), Predicate, source(Key),
                                   org(Path, Line)),
              Rows) ->
        print_rows(Rows)
    ;   true
    ).

:- pred print_rows(Rows) : list(Rows)
   # "Prints relation rows as tab-separated values.".

print_rows([]).
print_rows([Path-Line-Predicate|Rows]) :-
    format("~w\t~w\t~d~n", [Predicate, Path, Line]),
    print_rows(Rows).
