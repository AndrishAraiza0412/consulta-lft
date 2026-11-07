create extension if not exists vector;

-- ponytail: exact scan over about 1,100 articles; add HNSW if search latency matters.
create table if not exists chunks (
    id bigint generated always as identity primary key,
    source_version text not null,
    article text not null,
    part integer not null,
    text text not null,
    embedding vector(1024) not null,
    unique (source_version, article, part)
);

create table if not exists traces (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    question text not null,
    status text not null,
    retrieved jsonb not null default '[]',
    raw_answer text,
    model text not null,
    input_tokens integer not null default 0,
    output_tokens integer not null default 0,
    cost_usd numeric not null default 0,
    retrieval_ms integer,
    llm_ms integer,
    error text
);

create index if not exists traces_created_at on traces (created_at);
