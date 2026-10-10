#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_module('../ciao/workflow/agent_todos', [complete_agent_todo/2]).

main([Root, Fingerprint]) :-
    complete_agent_todo(Root, Fingerprint).
