-- Hybrid search: semantic ranking + structured filters (amount/status/state).
-- Vector similarity can't reason about "above $1M" or "still open"; these are
-- parsed from the query client-side and applied here as WHERE predicates.
create or replace function match_deals(
    query_embedding text,
    match_count   int     default 10,
    min_amount    numeric default null,   -- on total_offering_amount
    max_amount    numeric default null,
    status_filter text    default null,   -- 'open' | 'fully_subscribed'
    state_filter  text     default null    -- e.g. 'CA'
)
returns table (
    accession_number       text,
    entity_name            text,
    industry_group         text,
    total_offering_amount  numeric,
    total_amount_sold      numeric,
    total_remaining        numeric,
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
        f.total_remaining,
        f.status,
        i.city,
        i.state_or_country,
        f.federal_exemptions,
        1 - (e.embedding <=> (query_embedding)::vector) as similarity
    from filing_embeddings e
    join filings f using (accession_number)
    join issuers i using (cik)
    where (min_amount    is null or f.total_offering_amount >= min_amount)
      and (max_amount    is null or f.total_offering_amount <= max_amount)
      and (status_filter is null or f.status = status_filter)
      and (state_filter  is null or i.state_or_country = state_filter)
    order by e.embedding <=> (query_embedding)::vector
    limit match_count;
$$;
