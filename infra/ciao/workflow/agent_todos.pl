:- module(agent_todos, [
    refresh_agent_todos/1,
    complete_agent_todo/2,
    pending_agent_todo/5,
    agent_todo_source_hint/4,
    agent_action_authority/2,
    completion_precondition/1
], [assertions, regtypes, modes, doccomments]).

:- doc(title, "Episteme Agent Tasks").
:- doc(author, "Marco Pérez").
:- doc(module, "Exposes provisional @tt{:AGENT_TODO:} requests to librarian
agents without treating them as durable knowledge.

Task scope comes from the enclosing heading path. Source hints remain
provisional until they are materialized as citations or relations outside the
drawer. Action authority is explicit and independent from natural-language
classification performed by the agent. Completed tasks are removed only after
the requested durable outcome exists and repository validation succeeds.").

:- use_module('../org/org_snapshot', [
    refresh_snapshot/1,
    snapshot_valid/0,
    agent_todo/5,
    agent_todo_citation/4
]).
:- use_module(library(process), [process_call/3]).

:- regtype agent_note_ref/1 # "A durable note or an ID-less file reference.".
agent_note_ref(note(Id)) :- atm(Id).
agent_note_ref(file(Path)) :- atm(Path).

:- regtype agent_todo_origin/1 # "The complete source range of a task drawer.".
agent_todo_origin(org(Path, Start, End)) :-
    atm(Path),
    int(Start),
    int(End).

:- regtype agent_citation_locator/1 # "A provisional locator or @tt{no_locator}.".
agent_citation_locator(no_locator).
agent_citation_locator(locator(Value)) :- atm(Value).

:- regtype agent_citation_origin/1 # "The exact source-hint position.".
agent_citation_origin(org(Path, Line, Column)) :-
    atm(Path),
    int(Line),
    int(Column).

:- regtype agent_action/1 # "An action governed by the librarian policy.".
agent_action(edit_note).
agent_action(add_verified_citation).
agent_action(assign_required_id).
agent_action(propose_source).
agent_action(propose_relation).
agent_action(approve_source).
agent_action(import_source).
agent_action(accept_relation).
agent_action(move_note).
agent_action(merge_notes).
agent_action(delete_knowledge).
agent_action(external_action).

:- regtype agent_authority/1 # "Whether an action is autonomous or reviewed.".
agent_authority(autonomous).
agent_authority(human_approval).

:- regtype completion_requirement/1
   # "A condition required before removing a completed task.".
completion_requirement(requested_outcome_exists).
completion_requirement(required_approvals_complete).
completion_requirement(repository_validation_passes).
completion_requirement(task_content_is_unchanged).

:- pred refresh_agent_todos(+Root) : atm(Root)
   # "Refreshes the live Org snapshot rooted at @var{Root}.".

refresh_agent_todos(Root) :-
    refresh_snapshot(Root).

:- pred complete_agent_todo(+Root, +Fingerprint) : (atm(Root), atm(Fingerprint))
   # "Removes one unchanged task from a valid repository and refreshes the
      snapshot. The caller must first establish every declared completion
      precondition.".

complete_agent_todo(Root, Fingerprint) :-
    refresh_snapshot(Root),
    require_valid_snapshot,
    pending_agent_todo(Fingerprint, _, _, _, _),
    process_call('infra/bin/complete-agent-todo',
                 ['--root', '.', Fingerprint],
                 [cwd(Root), stdout(null)]),
    refresh_snapshot(Root),
    \+ pending_agent_todo(Fingerprint, _, _, _, _).

require_valid_snapshot :-
    (   snapshot_valid ->
        true
    ;   throw(error(invalid_org_snapshot,
                    complete_agent_todo/2))
    ).

:- pred pending_agent_todo(Fingerprint, NoteRef, HeadingPath, Body, Origin)
   => (atm(Fingerprint), agent_note_ref(NoteRef), list(atm, HeadingPath),
       atm(Body), agent_todo_origin(Origin))
   # "Enumerates a pending request and its section-local scope.".

pending_agent_todo(Fingerprint, NoteRef, HeadingPath, Body, Origin) :-
    agent_todo(Fingerprint, NoteRef, HeadingPath, Body, Origin).

:- pred agent_todo_source_hint(Fingerprint, Source, Locator, Origin)
   => (atm(Fingerprint), atm(Source), agent_citation_locator(Locator),
       agent_citation_origin(Origin))
   # "Enumerates a provisional citation hint contained in a request.".

agent_todo_source_hint(Fingerprint, Source, Locator, Origin) :-
    agent_todo_citation(Fingerprint, source(Source), Locator, Origin).

:- pred agent_action_authority(Action, Authority)
   => (agent_action(Action), agent_authority(Authority))
   # "Declares the maximum authority for librarian action @var{Action}.".

agent_action_authority(edit_note, autonomous).
agent_action_authority(add_verified_citation, autonomous).
agent_action_authority(assign_required_id, autonomous).
agent_action_authority(propose_source, autonomous).
agent_action_authority(propose_relation, autonomous).
agent_action_authority(approve_source, human_approval).
agent_action_authority(import_source, human_approval).
agent_action_authority(accept_relation, human_approval).
agent_action_authority(move_note, human_approval).
agent_action_authority(merge_notes, human_approval).
agent_action_authority(delete_knowledge, human_approval).
agent_action_authority(external_action, human_approval).

:- pred completion_precondition(Requirement)
   => completion_requirement(Requirement)
   # "Enumerates conditions required before deleting a completed drawer.".

completion_precondition(requested_outcome_exists).
completion_precondition(required_approvals_complete).
completion_precondition(repository_validation_passes).
completion_precondition(task_content_is_unchanged).
