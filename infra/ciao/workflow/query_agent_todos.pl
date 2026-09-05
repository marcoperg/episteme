#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_package([assertions]).

:- doc(title, "Episteme Agent Task CLI").
:- doc(author, "Marco Pérez").
:- doc(module, "Lists live librarian requests for command-line and MCP
integration testing.").

:- use_module('./agent_todos', [
    refresh_agent_todos/1,
    complete_agent_todo/2,
    pending_agent_todo/5,
    agent_todo_source_hint/4,
    agent_action_authority/2,
    completion_precondition/1
]).
:- use_module('../org/org_snapshot', [snapshot_issue/4,
    snapshot_valid/0]).
:- use_module(library(aggregates), [setof/3]).
:- use_module(library(format), [format/2]).

:- pred main(Args) : list(Args)
   # "Runs an agent-task query described by @var{Args}.".

main(Args) :-
    refresh_agent_todos('.'),
    run_query(Args).

:- pred run_query(Args) : list(Args)
   # "Dispatches an agent-task query against the current snapshot.".

run_query([list]) :- !,
    print_todos.
run_query([show, Fingerprint]) :- !,
    print_todo(Fingerprint).
run_query([complete, Fingerprint]) :- !,
    complete_agent_todo('.', Fingerprint).
run_query([policy]) :- !,
    print_policy.
run_query([validate]) :- !,
    print_validation.
run_query(_) :-
    format("usage: agent-todos {list|show FINGERPRINT|complete FINGERPRINT|policy|validate}~n", []),
    halt(2).

:- pred print_todos
   # "Prints one tab-separated row per pending task.".

print_todos :-
    (   setof(todo(Fingerprint, Path, Start, End, HeadingPath),
              todo_summary(Fingerprint, Path, Start, End, HeadingPath),
              Todos) ->
        print_todo_rows(Todos)
    ;   true
    ).

todo_summary(Fingerprint, Path, Start, End, HeadingPath) :-
    pending_agent_todo(Fingerprint, _, HeadingPath, _,
                       org(Path, Start, End)).

print_todo_rows([]).
print_todo_rows([todo(Fingerprint, Path, Start, End, HeadingPath)|Todos]) :-
    format("~w\t~w\t~d\t~d\t~q~n",
           [Fingerprint, Path, Start, End, HeadingPath]),
    print_todo_rows(Todos).

:- pred print_todo(+Fingerprint) : atm(Fingerprint)
   # "Prints one task, its scope, body, and provisional source hints.".

print_todo(Fingerprint) :-
    pending_agent_todo(Fingerprint, NoteRef, HeadingPath, Body,
                       org(Path, Start, End)), !,
    format("fingerprint: ~w~nnote: ~q~npath: ~w~nlines: ~d-~d~nscope: ~q~n",
           [Fingerprint, NoteRef, Path, Start, End, HeadingPath]),
    print_source_hints(Fingerprint),
    format("body:~n~w~n", [Body]).
print_todo(Fingerprint) :-
    format("unknown AGENT_TODO fingerprint: ~w~n", [Fingerprint]),
    halt(1).

print_source_hints(Fingerprint) :-
    agent_todo_source_hint(Fingerprint, Source, Locator, Origin),
    format("source-hint: ~w\t~q\t~q~n", [Source, Locator, Origin]),
    fail.
print_source_hints(_).

:- pred print_policy
   # "Prints action-authority and completion-precondition declarations.".

print_policy :-
    agent_action_authority(Action, Authority),
    format("action\t~w\t~w~n", [Action, Authority]),
    fail.
print_policy :-
    completion_precondition(Requirement),
    format("completion\t~w~n", [Requirement]),
    fail.
print_policy.

:- pred print_validation
   # "Prints current integrity issues and exits unsuccessfully on errors.".

print_validation :-
    snapshot_issue(Severity, Path, Line, Message),
    format("~w: ~w:~d: ~w~n", [Severity, Path, Line, Message]),
    fail.
print_validation :-
    (   snapshot_valid ->
        true
    ;   halt(1)
    ).
