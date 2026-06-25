-- RLS: public read-only. Writes go through the service_role key (bypasses RLS).
alter table issuers           enable row level security;
alter table filings           enable row level security;
alter table related_persons   enable row level security;
alter table recipients        enable row level security;
alter table filing_embeddings enable row level security;

create policy "public read" on issuers           for select using (true);
create policy "public read" on filings           for select using (true);
create policy "public read" on related_persons   for select using (true);
create policy "public read" on recipients        for select using (true);
create policy "public read" on filing_embeddings for select using (true);
