# Episteme Infrastructure

## Purpose

This directory contains the implementation that validates and queries Episteme.
Org notes remain authoritative. The infrastructure parses them into a complete,
versioned snapshot that Ciao validates before atomically installing it in memory.
No generated relation database needs to be synchronized or committed.

Run all commands below from the Episteme repository root. Python 3 is required
for parsing, validation, snapshot export, and task completion. Relation and
librarian queries require Ciao. Persistent multithreaded consumers must serialize
snapshot refreshes with queries because Ciao table invalidation is process-wide.

The shared parser deliberately excludes the entire `infra/` subtree from note
discovery. Org-roam should likewise be configured to exclude `infra/`, so
implementation documentation and fixtures are never indexed as knowledge notes.

## Layout

- `infra/bin/check-integrity` validates Org structure, links, IDs, relations,
  citations, and librarian request drawers.
- `infra/bin/export-org-snapshot` emits deterministic schema-versioned JSON for
  the Ciao snapshot provider.
- `infra/bin/complete-agent-todo` atomically removes one unchanged validated
  `:AGENT_TODO:` drawer by fingerprint.
- `infra/bin/build-relations` is the temporary parity oracle for the former
  generated-facts representation; normal queries do not use it.
- `infra/bin/query-relations` refreshes the snapshot and runs the relation CLI.
- `infra/bin/relation-toplevel` refreshes the snapshot and opens the stable Ciao
  relation API in an interactive top level.
- `infra/bin/agent-todos` refreshes the snapshot and exposes librarian request
  queries, policy, validation, and completion.
- `infra/python/episteme_org` is the shared Org parser and Python implementation
  for integrity checks, snapshot export, completion, and legacy parity.
- `infra/ciao/org` validates and provides the live in-memory Org snapshot.
- `infra/ciao/relations` contains the relation schema, typed query API, and CLI
  adapter.
- `infra/ciao/workflow` contains the stable librarian request API and CLI
  adapter.
- `infra/emacs` contains the citation and reverse-navigation integration.
- `infra/tests` contains Python, Ciao runtime, and Emacs ERT tests.

## Snapshot Lifecycle

`infra/bin/export-org-snapshot` uses the same parser as
`infra/bin/check-integrity`. The resulting JSON contains integrity issues,
relations, citation occurrences, note paths, directory contexts, and pending
librarian requests. `infra/ciao/org/org_snapshot.pl` validates the complete
protocol document before replacing the current snapshot. A parser, process, or
schema failure therefore leaves any previously installed state available.

```text
Episteme Org notes
  -> infra/python/episteme_org
  -> infra/bin/export-org-snapshot
  -> infra/ciao/org/org_snapshot.pl
  -> infra/ciao/relations and infra/ciao/workflow
  -> Ciao MCP, top level, CLI, and Emacs
```

The provider API in `infra/ciao/org/org_snapshot.pl` includes:

- `refresh_snapshot/1`, `snapshot_valid/0`, `snapshot_issue/4`, and
  `snapshot_version/1` for lifecycle and validation.
- `asserted/5`, `from_index/5`, and `to_index/5` for authored graph facts.
- `asserted_citation/5`, `citation_from_index/5`, and
  `citation_to_index/5` for exact citation occurrences.
- `note_index/3` and `context_parent_index/2` for note location and directory
  context.
- `agent_todo/5` and `agent_todo_citation/4` for provisional librarian data.

## Relation Data Model

The snapshot stores each identified assertion once:

```prolog
asserted(Id, Subject, Predicate, Object, Origin).
```

Current node forms are `note(Id)`, `source(CiteKey)`, and `context(Path)`.
`note(Id)` uses the note's file-level Org `:ID:`; origins independently retain
`org(Path, Line)`. Direct citations produce `cites` assertions, while file-level
`:RELATIONS:` entries produce their declared predicate. Citations inside
`:AGENT_TODO:` drawers remain provisional source hints and do not enter the
relation graph.

For every graph-participating note, the snapshot records current location and
the directory branch needed to classify it:

```prolog
note_index(note(Id), Path, context(Directory)).
context_parent_index(context(Directory), context(Parent)).
```

ID-bearing files without authored relations or citations remain outside this
projected graph, as do unrelated directory branches. A file move changes its
path and structural relations without changing its `note(Id)` identity.

Each direct citation also produces an occurrence:

```prolog
asserted_citation(Id, Note, Source, locator(Locator),
                  org(Path, Line, Column)).
```

`Locator` is the whitespace-normalized Org reference suffix, such as
`locator('p. 42')`, or `no_locator` when none was authored. Occurrences preserve
repeated citations as independently navigable evidence. Graph assertions carry
line but not column, so repeated citations of one source on one line can collapse
to one `cites` assertion; use the occurrence API for exact locations or counts.

## Relation API

The stable API in `infra/ciao/relations/episteme_relations.pl` provides:

- `asserted_relation/5` for exactly authored assertions and provenance.
- `citation_occurrence/5`, `citations_from/4`, and `citations_to/4` for exact
  citation lookup.
- `note_path/2`, `primary_context/2`, and `parent_context/2` for identity,
  location, and projected directory structure.
- `immediate_relation/3` for direct and non-transitive schema consequences.
- `relation/3` for immediate and explicitly enabled transitive consequences.
- `outgoing/3` and `incoming/3` for directional traversal.

Incoming navigation does not change a predicate. Traversing an `informed_by`
edge backwards retains `informed_by`; the separately declared inverse derives
an `informs` edge. The schema supports inverse, symmetric, transitive, and
subproperty declarations. Unknown predicates remain ordinary directed
relations and should not be given stronger semantics merely for convenience.

Query references to a Bibliotheca source:

```sh
infra/bin/query-relations references muller\&vogelMullerVogelAtlas1995
```

The tab-separated rows contain predicate, repository-relative path, line,
column, and locator. Relation-drawer assertions use the synthetic column `1`.
The Emacs `C-c B` command consumes these rows to open or select an exact
Episteme occurrence.

For exploratory queries:

```sh
infra/bin/relation-toplevel
```

```prolog
?- citations_to(source('sourceKey'), Note, Locator, Origin).
?- note_path(note(NoteId), Path).
?- primary_context(note(NoteId), Context).
?- asserted_relation(Id, note(NoteId), informed_by,
                     source('sourceKey'), Origin).
?- incoming(source('sourceKey'), Predicate, note(NoteId)).
?- outgoing(source('sourceKey'), informs, note(NoteId)).
```

## AGENT_TODO API

An exact uppercase `:AGENT_TODO:` drawer is provisional workflow data, not
durable knowledge. Its scope is the enclosing heading path. Citation syntax in
the drawer is exposed as a source hint but is neither validated as a durable
citation nor projected as a `cites` relation.

The stable API in `infra/ciao/workflow/agent_todos.pl` provides:

- `refresh_agent_todos/1` to refresh the shared live snapshot.
- `pending_agent_todo/5` to enumerate fingerprint, note reference, heading
  path, body, and complete source range.
- `agent_todo_source_hint/4` to enumerate provisional citation hints and their
  exact origins.
- `agent_action_authority/2` to distinguish autonomous actions from those that
  require human approval.
- `completion_precondition/1` to enumerate the requirements for deletion.
- `complete_agent_todo/2` to remove one unchanged task after validation and
  refresh the snapshot.

Completion requires the requested durable outcome to exist, all required
approvals to be complete, repository validation to pass, and task content to be
unchanged. The completion helper uses an atomic same-directory replacement and
preserves ordinary file metadata.

```sh
infra/bin/agent-todos list
infra/bin/agent-todos show FINGERPRINT
infra/bin/agent-todos policy
infra/bin/agent-todos validate
infra/bin/agent-todos complete FINGERPRINT
```

`list` emits one tab-separated row per pending request. `show` includes scope,
body, and provisional source hints. `policy` reports action authority and
completion preconditions. `validate` prints snapshot issues and exits
unsuccessfully when errors exist.

## Emacs

Add `infra/emacs` to `load-path` and exclude `infra/` from Org-roam discovery:

```emacs-lisp
(setq org-roam-directory (file-truename "~/knowledge/episteme")
      org-roam-file-exclude-regexp "/infra/")

(add-to-list 'load-path
             (expand-file-name "~/knowledge/episteme/infra/emacs"))
(require 'episteme-citations)
```

`episteme-citations.el` defaults to `infra/bin/query-relations` beneath
`episteme-directory`. Customize `episteme-directory`,
`episteme-bibliotheca-file`, or `episteme-relation-query` for a different
checkout layout.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s infra/tests -v
emacs --batch -Q -L infra/emacs -l infra/tests/episteme-citations-test.el \
  -f ert-run-tests-batch-and-exit
infra/bin/check-integrity
infra/bin/export-org-snapshot >/dev/null
infra/bin/agent-todos validate
ciaopp -V infra/ciao/org/org_snapshot.pl
ciaopp -V infra/ciao/relations/relation_schema.pl
ciaopp -V infra/ciao/relations/episteme_relations.pl
ciaopp -V infra/ciao/workflow/agent_todos.pl
```

The expected CiaoPP baseline is zero false assertions. Analysis of the tabled
relation module can still report unverified contracts and unknown internal
tabling predicates because CiaoPP does not model that package completely.
`infra/tests/check_relation_semantics.pl` supplies runtime coverage for authored
provenance, incoming traversal, semantic inversion, citation lookup, and
librarian workflow behavior.
