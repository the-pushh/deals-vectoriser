-- Add pagination (match_offset) to match_deals. Adding a param changes the
-- signature, which would create a 3rd overload — so drop the 6-arg version first,
-- then create the 7-arg one. Keeps exactly one match_deals.
drop function if exists match_deals(text, integer, numeric, numeric, text, text);

create or replace function match_deals(
    query_embedding text,
    match_count   int     default 20,
    match_offset  int     default 0,
    min_amount    numeric default null,
    max_amount    numeric default null,
    status_filter text    default null,
    state_filter  text    default null
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
    limit match_count offset match_offset;
$$;
