-- 0005 added params to match_deals, but Postgres treats the new arg list as a
-- separate function — leaving the original 2-arg version from 0004 in place.
-- PostgREST then can't resolve no-filter calls (only 2 args sent). Drop the old one;
-- the 6-arg version with defaults handles every call.
drop function if exists match_deals(text, integer);
