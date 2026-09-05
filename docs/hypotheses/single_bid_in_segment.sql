-- Version-2 population and base-rate query for single_bid_in_segment.md.
--
-- Run against the dataset `serenata normalise` writes, with DuckDB:
--
--     duckdb -c ".read docs/hypotheses/single_bid_in_segment.sql"
--
-- from the repository root, with data/normalised/ populated. Reading Parquet
-- directly rather than through a database keeps this rerunnable by anyone who
-- has the archive: same packages in, same numbers out (ADR-0001).
--
-- Version 2 has NOT been remeasured. Counts below are historical VERSION 1,
-- measured 2026-09-04 over OJ S 52, 94, 113, 157 and 168 of 2026 (19,180
-- notices). This query no longer claims to reproduce those counts: duplicate
-- key validation, unanimous buyer country, statistic-code status and exact
-- whole-count validation change the population. Use the version-1 query in
-- repository history for old counts.

CREATE OR REPLACE VIEW lot_result_statistic AS
  SELECT * FROM read_parquet('data/normalised/lot_result_statistic/**/*.parquet',
                             hive_partitioning = true);
CREATE OR REPLACE VIEW lot_result AS
  SELECT * FROM read_parquet('data/normalised/lot_result/**/*.parquet',
                             hive_partitioning = true);
CREATE OR REPLACE VIEW lot AS
  SELECT * FROM read_parquet('data/normalised/lot/**/*.parquet',
                             hive_partitioning = true);
CREATE OR REPLACE VIEW procedure AS
  SELECT * FROM read_parquet('data/normalised/procedure/**/*.parquet',
                             hive_partitioning = true);
CREATE OR REPLACE VIEW organisation AS
  SELECT * FROM read_parquet('data/normalised/organisation/**/*.parquet',
                             hive_partitioning = true);
CREATE OR REPLACE VIEW organisation_role AS
  SELECT * FROM read_parquet('data/normalised/organisation_role/**/*.parquet',
                             hive_partitioning = true);

-- Fail closed BEFORE joining. Do not deduplicate identical rows or choose
-- among conflicting rows, even across years. Errors expose no record values.
-- Structural keys match the normalised model; local join IDs and a single
-- present tender-code block per lot result are additional requirements.
CREATE OR REPLACE VIEW duplicate_input_keys AS
SELECT 1 FROM procedure
GROUP BY source_publication_id HAVING count(*) > 1
UNION ALL
SELECT 1 FROM lot
GROUP BY source_publication_id, ordinal HAVING count(*) > 1
UNION ALL
SELECT 1 FROM lot_result
GROUP BY source_publication_id, ordinal HAVING count(*) > 1
UNION ALL
SELECT 1 FROM organisation
GROUP BY source_publication_id, ordinal HAVING count(*) > 1
UNION ALL
SELECT 1 FROM organisation_role
GROUP BY source_publication_id, role, scope_table, scope_ordinal, block_ordinal
HAVING count(*) > 1
UNION ALL
SELECT 1 FROM lot_result_statistic
GROUP BY source_publication_id, lot_result_ordinal, statistic_kind, block_ordinal
HAVING count(*) > 1
UNION ALL
SELECT 1 FROM lot WHERE lot_id IS NOT NULL
GROUP BY source_publication_id, lot_id HAVING count(*) > 1
UNION ALL
SELECT 1 FROM organisation WHERE org_local_id IS NOT NULL
GROUP BY source_publication_id, org_local_id HAVING count(*) > 1
UNION ALL
SELECT 1 FROM lot_result_statistic
WHERE statistic_kind = 'received_submissions' AND statistic_code = 'tenders'
  AND statistic_code_status = 'present'
GROUP BY source_publication_id, lot_result_ordinal HAVING count(*) > 1;

SELECT CASE WHEN EXISTS (SELECT 1 FROM duplicate_input_keys)
            THEN error('duplicate classifier input keys') ELSE true END;

-- The buyer's country. Organisation identifiers are scoped to their notice, so
-- this join is within one publication and never across notices: cross-notice
-- organisation identity is milestone 3 and is not assumed here. Every buyer
-- must resolve to a present country and all must agree; min is only used after
-- proving there is exactly one country, never to choose among alternatives.
CREATE OR REPLACE VIEW buyer_country AS
SELECT r.source_publication_id,
       min(o.country_code) AS country
FROM organisation_role r
LEFT JOIN organisation o
  ON o.source_publication_id = r.source_publication_id
 AND o.org_local_id = r.org_ref
WHERE r.role = 'buyer'
GROUP BY 1
HAVING count(DISTINCT o.country_code) = 1
   AND count(*) = count(*) FILTER (
       WHERE o.country_code_status = 'present'
         AND o.country_code IS NOT NULL AND o.country_code <> ''
   );

-- One row per lot outcome the rule can speak about. Every exclusion here is
-- argued in the hypothesis file: withheld counts are not numbers, zero bids is
-- not one bid, a procedure with no call for competition is not expected to
-- attract several, and a framework's competition happens at call-off.
CREATE OR REPLACE VIEW population AS
-- Numeric values remain strings; parse already strips outer whitespace.
-- Accept optional +, ASCII digits and an optional dot with only zeros after it.
-- Check the entire string before discarding its zero fraction. Cast only the
-- integer part: casting decimals, even with TRY_CAST, can round nonzero tails.
-- TRY_CAST excludes BIGINT overflow; bids >= 1 excludes zero below.
WITH counted_statistics AS (
    SELECT *,
      CASE WHEN regexp_full_match(statistic_value, '[+]?[0-9]+([.]0*)?')
      THEN TRY_CAST(split_part(statistic_value, '.', 1) AS BIGINT)
      END AS bids
    FROM lot_result_statistic
)
SELECT s.source_publication_id,
       s.lot_result_ordinal,
  s.bids,
       b.country,
       substr(l.cpv_code, 1, 2) AS division
FROM counted_statistics s
JOIN lot_result lr
  ON lr.source_publication_id = s.source_publication_id
 AND lr.ordinal = s.lot_result_ordinal
JOIN lot l
  ON l.source_publication_id = s.source_publication_id
 AND l.lot_id = lr.lot_ref
JOIN procedure p
  ON p.source_publication_id = s.source_publication_id
JOIN buyer_country b
  ON b.source_publication_id = s.source_publication_id
WHERE s.statistic_kind = 'received_submissions'
  AND s.statistic_code = 'tenders'
  AND s.statistic_code_status = 'present'
  AND s.statistic_value_status = 'present'
  AND s.bids >= 1
  AND p.procedure_code_status = 'present'
  AND p.procedure_code IN ('open', 'restricted', 'comp-dial', 'comp-tend',
                           'innovation', 'neg-w-call')
  AND l.cpv_code_status = 'present'
  AND NOT list_has_any(l.contracting_system_codes,
                       ['fa-wo-rc', 'fa-w-rc', 'fa-mix', 'dps-list', 'dps-nlist']);

-- The segment baseline: buyer country and CPV division, over this dataset.
CREATE OR REPLACE VIEW segment AS
SELECT country, division,
       count(*) AS lot_results,
       100.0 * count(*) FILTER (WHERE bids = 1) / count(*) AS single_bid_rate
FROM population
GROUP BY 1, 2;

-- 1. The population, and the rate case 001 was rejected on.
--    Historical v1: 8,159 lot results, 3,435 single bid (42.1%), 3,790 notices.
SELECT count(*)                             AS lot_results,
       count(*) FILTER (WHERE bids = 1)     AS single_bid,
       count(DISTINCT source_publication_id) AS notices
FROM population;

-- 2. How far segments differ. Historical v1: 26 segments of 50 or more, covering
--    4,299 lot results (52.7%), rates from 6.5% to 78.2%, median 35.2%.
SELECT count(*)                       AS segments,
       sum(lot_results)               AS covered,
       round(min(single_bid_rate), 1) AS lowest,
       round(median(single_bid_rate), 1) AS median,
       round(max(single_bid_rate), 1) AS highest
FROM segment
WHERE lot_results >= 50;

-- 3. The flags. Historical v1: 96 flags in 71 notices, 2.23% of the covered
--    population.
SELECT count(*)                              AS flags,
       count(DISTINCT p.source_publication_id) AS notices
FROM population p
JOIN segment g USING (country, division)
WHERE g.lot_results >= 50
  AND g.single_bid_rate < 15
  AND p.bids = 1;
