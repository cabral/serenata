-- Base rate for docs/hypotheses/single_bid_in_segment.md.
--
-- Run against the dataset `serenata normalise` writes, with DuckDB:
--
--     duckdb -c ".read docs/hypotheses/single_bid_in_segment.sql"
--
-- from the repository root, with data/normalised/ populated. Reading Parquet
-- directly rather than through a database keeps this rerunnable by anyone who
-- has the archive: same packages in, same numbers out (ADR-0001).
--
-- Measured 2026-09-04 over OJ S 52, 94, 113, 157 and 168 of 2026 --- 19,180
-- notices. The classifier applies the same definitions in Python over the same
-- rows; this file is what makes the measurement checkable without running it.

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

-- The buyer's country. Organisation identifiers are scoped to their notice, so
-- this join is within one publication and never across notices: cross-notice
-- organisation identity is milestone 3 and is not assumed here.
CREATE OR REPLACE VIEW buyer_country AS
SELECT r.source_publication_id,
       any_value(o.country_code) AS country
FROM organisation_role r
JOIN organisation o
  ON o.source_publication_id = r.source_publication_id
 AND o.org_local_id = r.org_ref
WHERE r.role = 'buyer'
  AND o.country_code_status = 'present'
GROUP BY 1;

-- One row per lot outcome the rule can speak about. Every exclusion here is
-- argued in the hypothesis file: withheld counts are not numbers, zero bids is
-- not one bid, a procedure with no call for competition is not expected to
-- attract several, and a framework's competition happens at call-off.
CREATE OR REPLACE VIEW population AS
SELECT s.source_publication_id,
       s.lot_result_ordinal,
       CAST(s.statistic_value AS BIGINT) AS bids,
       b.country,
       substr(l.cpv_code, 1, 2) AS division
FROM lot_result_statistic s
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
  AND s.statistic_value_status = 'present'
  AND TRY_CAST(s.statistic_value AS BIGINT) >= 1
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
--    Measured: 8,159 lot results, 3,435 single bid (42.1%), 3,790 notices.
SELECT count(*)                             AS lot_results,
       count(*) FILTER (WHERE bids = 1)     AS single_bid,
       count(DISTINCT source_publication_id) AS notices
FROM population;

-- 2. How far segments differ. Measured: 26 segments of 50 or more, covering
--    4,299 lot results, rates from 6.5% to 78.2%, median 35.2%.
SELECT count(*)                       AS segments,
       sum(lot_results)               AS covered,
       round(min(single_bid_rate), 1) AS lowest,
       round(median(single_bid_rate), 1) AS median,
       round(max(single_bid_rate), 1) AS highest
FROM segment
WHERE lot_results >= 50;

-- 3. The flags. Measured: 96 flags in 71 notices, 2.23% of the covered
--    population.
SELECT count(*)                              AS flags,
       count(DISTINCT p.source_publication_id) AS notices
FROM population p
JOIN segment g USING (country, division)
WHERE g.lot_results >= 50
  AND g.single_bid_rate < 15
  AND p.bids = 1;
