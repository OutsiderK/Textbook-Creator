# Reference Chapter Annotation

This annotation explains the presentation choices in `spec/reference-chapter.md`. Do not copy these notes into real chapters.

## SVG

The queue-length state transition is shown as an SVG because the concept is a state machine: states, events, transitions, and boundary behavior matter at the same time. A paragraph can explain the idea, but the diagram lets the reader scan the skeleton first.

## Formula

The utilization equation is paired with a variable table. The formula alone is too compact for learners who have not memorized the symbols; the table keeps the quantitative relationship auditable.

## Highlight

`==rho 小于 1 是稳定的必要负载条件，不是低延迟保证==` is highlighted because it is an exam-style distinction. The chapter does not highlight ordinary definitions like "arrival rate is tasks per unit time".

## Table

The service-rate/utilization/stability comparison is a table because the teaching task is comparison across dimensions. A prose paragraph would make the same distinctions harder to scan.

## Callouts

`核心判断` states the central conceptual boundary. `易错点` prevents a common overgeneralization. Both are short enough to stay useful rather than becoming decorative blocks.

## Grouping

The chapter uses one figure, one formula block, one comparison table, and one ordered list. It demonstrates visual density and component rhythm, not a fixed template every chapter must copy.
