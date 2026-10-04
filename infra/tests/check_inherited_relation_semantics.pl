#!/usr/bin/env ciao-shell
% -*- mode: ciao; -*-

:- use_module('../ciao/relations/episteme_relations', [
    asserted_relation/5,
    inherited_relation/5,
    relation/3
]).
:- use_module('../ciao/org/org_snapshot', [
    refresh_snapshot/1,
    snapshot_valid/0,
    snapshot_version/1
]).

main([Root]) :-
    refresh_snapshot(Root),
    snapshot_version(2),
    snapshot_valid,
    Course = context(course),
    Nested = context('course/nested'),
    Source = source('courseSource'),
    NestedSource = source('nestedSource'),
    Readme = note('readme-id'),
    Topic = note('topic-id'),
    NestedTopic = note('nested-id'),
    asserted_relation(_, Course, informed_by, Source,
                      org('course/README.org', 9)),
    asserted_relation(_, Readme, informed_by, source('readmeSource'),
                      org('course/README.org', 6)),
    inherited_relation(Topic, informed_by, Source, Course,
                       org('course/README.org', 9)),
    inherited_relation(NestedTopic, informed_by, Source, Course,
                       org('course/README.org', 9)),
    inherited_relation(NestedTopic, informed_by, NestedSource, Nested,
                       org('course/nested/README.org', 3)),
    relation(Topic, informed_by, Source),
    relation(Source, informs, Topic),
    relation(NestedTopic, informed_by, Source),
    relation(NestedTopic, informed_by, NestedSource),
    \+ inherited_relation(Readme, informed_by, Source, _, _),
    \+ relation(Topic, cites, Source).
