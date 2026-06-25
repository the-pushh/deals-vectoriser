-- Semantic search: cosine match over filing_embeddings, joined to issuer/filing facts.
-- query_embedding is passed as text ('[...]') and cast to vector here, which avoids
-- PostgREST RPC type-coercion ambiguity.
create or replace function match_deals(query_embedding text, match_count int default 10)
returns table (
    accession_number       text,
    entity_name            text,
    industry_group         text,
    total_offering_amount  numeric,
    total_amount_sold      numeric,
    status                 text,
    city                   text,
    state_or_country       text,
    federal_exemptions     text[],
    similarity             double precision
)
language sql
stable
as $$
    select
        f.accession_number,
        i.entity_name,
        f.industry_group,
        f.total_offering_amount,
        f.total_amount_sold,
        f.status,
        i.city,
        i.state_or_country,
        f.federal_exemptions,
        1 - (e.embedding <=> (query_embedding)::vector) as similarity
    from filing_embeddings e
    join filings f using (accession_number)
    join issuers i using (cik)
    order by e.embedding <=> (query_embedding)::vector
    limit match_count;
$$;
