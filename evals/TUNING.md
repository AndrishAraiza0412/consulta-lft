# Tuning log

Every change below was decided on the `dev` split only. The `test` split runs once, on a frozen commit, after tuning ends.

| Round | Change | Why | Dev accuracy |
|---|---|---|---|
| 0 | Baseline: `top_k=5`, `min_similarity=0.5`, original prompt | Starting point | 42/60 (70%); direct 18/24, multi 0/12 |
| 1 | Prompt: explain the `[Art. N]` labels, require at least one citation, give one format example (Art. 132, used by no case), answer when the context covers the question in part | Retrieval found the expected article in 11/12 cases, yet 9 runs answered correctly without citations and 6 said NO_ENCONTRADO with the right article ranked first | 36/60 (60%); direct 6/24, multi 6/12. Worse: many replies were only the citation, e.g. `[Art. 87]` |
| 2 | Prompt: give the concrete data first, then the citation; a citation-only reply is useless | Round 1 fixed missing citations but produced citation-only replies | pending |

Grader fix during round 1: facts split by a line break (`media\nhora`) were not matched. Whitespace is now collapsed before matching, and both earlier runs were regraded from their stored answers; the round 0 total did not change, round 1 went from 33/60 to 36/60. The stored result files keep the grades they were produced with.
