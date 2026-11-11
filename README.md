# Consulta LFT

A question-answering assistant over Mexico's Federal Labor Law (Ley Federal del Trabajo, LFT). It answers in Spanish, cites the articles it used, checks those citations in code, and says "I don't know" when the law does not cover the question. A 40-case evaluation measures how often it gets that right.

It runs entirely on a laptop: a 3B-parameter model through Ollama, PostgreSQL with pgvector, no API keys.

## Results

Held-out `test` split, run once on the frozen system: 20 cases, 3 runs each. The `dev` split was used for every tuning decision.

| Metric | test | dev |
|---|---|---|
| **Accuracy** | **48/60 (80%)** | 45/60 (75%) |
| Direct answer | 15/24 (62%) | 15/24 (62%) |
| Several articles | 9/12 (75%) | 6/12 (50%) |
| Outside the law → "I don't know" | 15/15 (100%) | 15/15 (100%) |
| Prompt-injection attacks resisted | 9/9 (100%) | 9/9 (100%) |
| Correct citations, among answered runs | 24/24 (100%) | 21/27 (78%) |
| Undue "I don't know" on answerable questions | 12/36 (33%) | 9/36 (25%) |
| Expected article retrieved (top 5), per case | 11/12 (92%) | 11/12 (92%) |
| Latency, median / p95 | 1.0 s / 4.1 s | 0.8 s / 2.9 s |

Model `qwen2.5:3b-instruct`, embeddings `bge-m3`, on an 8 GB Apple M2. Full reports: [`evals/results/`](evals/results/).

**What it gets right.** Questions outside the law (World Cup, SQL, ISR tax rates, IMSS contributions) got "I don't know" every time. 4 of the 10 out-of-scope cases were refused before the model was called, because no article was similar enough; in the other 6 (including ISR and IMSS) the model itself replied `NO_ENCONTRADO`. Injected instructions, fake context and requests to invent articles never produced the forbidden content.

**What it gets wrong.** The dominant failure is being too cautious: in all 4 failed `test` cases the expected article was ranked first, and the 3B model still replied `NO_ENCONTRADO` or only a bare citation. In `dev`, other failures were citing a neighbouring article (60 instead of 61), a two-article question answered wrongly although both articles were retrieved (76/80), and one where neither article was retrieved (73/75).

**A limit of the citation check.** The code verifies that every cited article was in the model's context. It does not verify that the article supports the sentence. During tuning, the model copied a sentence from a prompt example and attached the question's article to it, and the check passed. That prompt was reverted; the gap remains.

## How it works

```
data/LFT.pdf ─► parse by article ─► bge-m3 ─► PostgreSQL + pgvector
                                                  ▲
React ─► FastAPI POST /ask ─► embed question ─► top 5 by cosine similarity
                                │
                                ├─ none above threshold ──► "I don't know" (no LLM call)
                                ├─ Qwen answers from ≤ 6,000 chars of context
                                ├─ citations checked against the articles in that context
                                └─ trace row: retrieved articles, tokens, cost, latency
```

1. **Ingestion** extracts the official PDF, removes page headers and gazette notes (`Artículo reformado DOF …`), splits it by article (`153-A`, `22 Bis`, `3o. Ter` included) and stops before the transitory articles. 1,266 articles; the 145 repealed ones get no embedding.
2. **Retrieval** returns the 5 most similar chunks. Below a similarity of 0.5 the answer is "I don't know".
3. **Generation** asks for `[Art. N]` citations and treats the context and question as data, not instructions.
4. **Validation** rejects an answer with no verifiable citation, a bare citation with no text, or `NO_ENCONTRADO`. Citations to articles outside the context are returned separately and flagged in the UI.
5. **Budget** blocks requests once the month's traced cost reaches `MONTHLY_LIMIT_USD`. With Ollama the price is 0, so this is covered by unit tests only.

## Decisions

| Decision | Why |
|---|---|
| pgvector, not a separate vector store | One database; similarity search is a SQL query |
| No LangChain | The pipeline is about 150 lines and each step can be explained |
| OpenAI-compatible client against Ollama | Moving to a paid API changes three environment variables |
| `bge-m3` embeddings | Multilingual; fits in 8 GB next to Qwen (measured: 16% memory free) |
| `pdfplumber`, not `pypdf` | `pypdf` split words in this PDF ("riesg o") |
| Traces in a Postgres table, not Langfuse | Self-hosted Langfuse is heavy for 8 GB; LangSmith needs a cloud account |
| Exact vector scan, no index | 1,478 chunks; an HNSW index is not worth it yet |
| Separate `dev` and `test` splits | Tuning on the cases you report inflates the number |

## Evaluation method

[`evals/cases.json`](evals/cases.json) has 40 cases written from the article text: 16 direct, 8 multi-article, 10 outside the law, 6 attacks, split evenly between `dev` and `test`. Grading is rule-based: required facts (with accepted variants, ignoring case and accents), expected articles, forbidden content for attacks.

Tuning used `dev` only, three rounds, one change each, logged in [`evals/TUNING.md`](evals/TUNING.md). Two of the three prompt changes made things worse before the third improved on the baseline (70% → 75%). The runner refuses to run `test` on an uncommitted tree and stamps every result with its commit.

## Run it

Requirements: Docker, [Ollama](https://ollama.com) on the host, about 4 GB free memory.

```bash
ollama pull qwen2.5:3b-instruct
ollama pull bge-m3
docker compose up -d --build
docker compose exec api .venv/bin/python -m app.ingest data/LFT.pdf   # about 3 minutes
open http://127.0.0.1:8080
```

Ollama stays on the host because inside Docker on a Mac it would have no GPU.

### Develop and test

```bash
docker compose up -d db
uv sync
uv run pytest                 # 114 tests; uses a real pgvector database and a fake LLM
uv run uvicorn app.main:app --port 8000
cd web && npm ci && npm run dev && npx vitest run
```

### Re-run the evaluation

```bash
uv run uvicorn app.main:app --port 8000   # in another terminal
uv run python -m evals.run --split dev    # about 5 minutes
```

### Read the traces

```sql
select created_at, status, left(question, 50) as question,
       retrieved -> 0 ->> 'article' as top_article, input_tokens, output_tokens, llm_ms
from traces order by created_at desc limit 20;
```

## Known limits

- **One version of the law**: the PDF published with the reform of 14 May 2026, SHA-256 in [`data/LFT.pdf.sha256`](data/LFT.pdf.sha256). Later reforms are not included.
- **Not legal advice.** The UI says so on every page.
- **Small model.** A larger model would likely reduce undue "I don't know" answers; that has not been measured here.
- **Cost limits** are tested with configured prices only; no paid API was used.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) has not run yet; it runs on the first push.
- The Qwen 2.5 3B model is under the Qwen Research License; check it before any commercial use.

## AI usage

This project was built with Claude Code as a coding assistant, working from a written spec and plan in [`docs/superpowers/`](docs/superpowers/). I chose the project, the corpus and the scope, approved the design, and reviewed a sample of the evaluation cases before the held-out run. Every result in this README comes from a file in `evals/results/`.
