-- Extensions: pgvector for embeddings, pg_trgm for fuzzy name search.
create extension if not exists vector;
create extension if not exists pg_trgm;
