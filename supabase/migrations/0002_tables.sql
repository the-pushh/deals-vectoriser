-- Core schema. One issuer -> many filings -> child tables. Embeddings 1:1 with filing.

-- Issuers: one row per CIK (deduped across filings).
create table if not exists issuers (
    cik                     text primary key,
    entity_name             text,
    entity_type             text,
    jurisdiction_of_inc     text,
    year_of_inc             smallint,
    within_five_years       boolean,
    sic_code                text,
    sic_description         text,
    ein                     text,
    state_of_incorporation  text,
    street1                 text,
    street2                 text,
    city                    text,
    state_or_country        text,
    state_or_country_desc   text,
    zip_code                text,
    phone                   text,
    previous_names          text[] default '{}',
    former_names            text[] default '{}',
    updated_at              timestamptz default now()
);

-- Filings: one row per accession (full history, incl. D/A amendments).
create table if not exists filings (
    accession_number        text primary key,
    cik                     text references issuers(cik),
    form_type               text,
    is_amendment            boolean,
    filed_date              date,
    date_of_first_sale      date,
    yet_to_occur            boolean,
    industry_group          text,
    revenue_range           text,
    federal_exemptions      text[] default '{}',
    security_types          text[] default '{}',
    more_than_one_year      boolean,
    is_business_combination boolean,
    minimum_investment      numeric,
    total_offering_amount   numeric,
    is_indefinite           boolean default false,
    total_amount_sold       numeric,
    total_remaining         numeric,
    has_non_accredited      boolean,
    num_investors           integer,
    sales_commissions       numeric,
    finders_fees            numeric,
    use_of_proceeds         numeric,
    filing_url              text,
    -- best-effort subscription state; 'stale' is computed at query time (needs now()).
    status                  text generated always as (
        case when total_remaining is not null and total_remaining <= 0
             then 'fully_subscribed' else 'open' end
    ) stored,
    raw                     jsonb,
    created_at              timestamptz default now()
);

create index if not exists filings_cik_idx        on filings (cik);
create index if not exists filings_industry_idx   on filings (industry_group);
create index if not exists filings_filed_date_idx on filings (filed_date desc);
create index if not exists filings_status_idx     on filings (status);

-- Related persons (execs, directors, promoters) per filing.
create table if not exists related_persons (
    id                bigint generated always as identity primary key,
    accession_number  text references filings(accession_number) on delete cascade,
    full_name         text,
    relationships     text[] default '{}',
    city              text,
    state             text
);
create index if not exists related_persons_acc_idx on related_persons (accession_number);

-- Sales-compensation recipients (brokers/finders) per filing.
create table if not exists recipients (
    id                bigint generated always as identity primary key,
    accession_number  text references filings(accession_number) on delete cascade,
    recipient_name    text,
    crd_number        text,
    states_solicited  text[] default '{}'
);
create index if not exists recipients_acc_idx on recipients (accession_number);

-- Embeddings: one composed deal-text + vector per filing.
create table if not exists filing_embeddings (
    accession_number  text primary key references filings(accession_number) on delete cascade,
    content           text,
    content_tsv       tsvector generated always as (to_tsvector('english', coalesce(content, ''))) stored,
    embedding         vector(1536),
    model             text,
    created_at        timestamptz default now()
);

create index if not exists filing_embeddings_hnsw
    on filing_embeddings using hnsw (embedding vector_cosine_ops);
create index if not exists filing_embeddings_tsv_idx
    on filing_embeddings using gin (content_tsv);

create index if not exists issuers_name_trgm_idx
    on issuers using gin (entity_name gin_trgm_ops);
