# Tuning log

Every change below was decided on the `dev` split only. The `test` split runs once, on a frozen commit, after tuning ends.

| Round | Change | Why | Dev accuracy |
|---|---|---|---|
| 0 | Baseline: `top_k=5`, `min_similarity=0.5`, original prompt | Starting point | 42/60 (70%) |
| 1 | Prompt: explain the `[Art. N]` labels, require at least one citation, give one format example (Art. 132, used by no case), answer when the context covers the question in part | Retrieval found the expected article in 11/12 cases, yet 9 runs answered correctly without citations and 6 said NO_ENCONTRADO with the right article ranked first | pending |
