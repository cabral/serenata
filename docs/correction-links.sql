-- Structural measurement of correction links, for correction-links.md.
--
-- Run against the dataset `serenata normalise` writes, with DuckDB:
--
--     duckdb -c ".read docs/correction-links.sql"
--
-- from the repository root, with data/normalised/ populated. Same packages in,
-- same numbers out (ADR-0001). Open work #6 requires this measurement before a
-- correction mapping is designed, so the design can cite structure rather than
-- assume it.
--
-- Counts and shapes only. No identifier, notice or field value is selected:
-- every statement returns aggregates, and the pattern tests return how many
-- values match a shape, never which values they were.

CREATE OR REPLACE VIEW notice AS
  SELECT * FROM read_parquet('data/normalised/notice/**/*.parquet',
                             hive_partitioning = true);

-- 1. How many notices carry a correction link at all.
--    Measured: 19,180 notices; 2,840 present (14.8%), 16,340 absent.
SELECT changed_notice_id_status, count(*) AS notices
FROM notice GROUP BY 1 ORDER BY 2 DESC;

-- 2. Which identifier namespace the link uses. The field is polymorphic: two
--    unrelated shapes appear in one column, so a mapping must detect the
--    namespace rather than assume one.
--    Measured: 1,752 eForms UUID + '-NN' (61.7%); 1,088 digits-digits (38.3%),
--    of lengths 11, 10 and 9 (1,055 / 30 / 3). Nine distinct suffixes.
SELECT
  count(*) FILTER (
    WHERE regexp_full_match(changed_notice_id,
      '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[0-9]{2}')
  ) AS eforms_uuid_versioned,
  count(*) FILTER (
    WHERE regexp_full_match(changed_notice_id, '[0-9]+-[0-9]+')
  ) AS legacy_number_year,
  count(DISTINCT regexp_extract(changed_notice_id, '-([0-9]{2})$', 1)) AS suffixes,
  count(*) AS present_links
FROM notice WHERE changed_notice_id_status = 'present';

SELECT length(changed_notice_id) AS link_length, count(*) AS links
FROM notice WHERE changed_notice_id_status = 'present'
GROUP BY 1 ORDER BY 2 DESC;

-- 3. Whether the link resolves inside this corpus, before and after removing
--    the two-digit version suffix. A corrigendum usually corrects a notice
--    published on another day, so a low rate over five sampled days measures
--    corpus coverage, not a broken mapping.
--    Measured: 0 of 2,840 raw; 45 of 2,840 (1.6%) after stripping '-NN'.
CREATE OR REPLACE VIEW link AS
SELECT source_notice_id,
       regexp_replace(changed_notice_id, '-[0-9]{2}$', '') AS target
FROM notice WHERE changed_notice_id_status = 'present';

SELECT
  (SELECT count(*) FROM notice n WHERE n.changed_notice_id_status = 'present'
     AND EXISTS (SELECT 1 FROM notice t
                 WHERE t.source_notice_id = n.changed_notice_id)) AS resolved_raw,
  (SELECT count(*) FROM link l
     WHERE EXISTS (SELECT 1 FROM notice t
                   WHERE t.source_notice_id = l.target)) AS resolved_stripped,
  (SELECT count(*) FROM link) AS present_links;

-- 4. Ambiguity and chains. Two notices correcting one target have no
--    authoritative order in the data alone; a chain needs both ends archived.
--    Measured: 2,832 distinct targets, 7 referenced more than once,
--    0 chains of depth 2 within the corpus, 0 self-references.
SELECT
  (SELECT count(DISTINCT target) FROM link) AS distinct_targets,
  (SELECT count(*) FROM (SELECT target FROM link GROUP BY 1 HAVING count(*) > 1))
    AS targets_referenced_more_than_once,
  (SELECT count(*) FROM notice a JOIN notice b
     ON b.changed_notice_id = a.source_notice_id
   WHERE a.changed_notice_id_status = 'present'
     AND b.changed_notice_id_status = 'present') AS chains_of_depth_two,
  (SELECT count(*) FROM notice WHERE changed_notice_id_status = 'present'
     AND changed_notice_id = source_notice_id) AS self_references;

-- 5. Which notice kinds carry corrections. The single-bid rule reads award
--    notices, so that row bounds what correction handling changes for it.
--    Measured: ContractNotice 2,695; ContractAwardNotice 118;
--    PriorInformationNotice 27.
SELECT root_element, count(*) AS corrected_notices
FROM notice WHERE changed_notice_id_status = 'present'
GROUP BY 1 ORDER BY 2 DESC;

-- 6. Version identity is populated and does move.
--    Measured: 01 = 18,153; 02 = 699; 03 = 123; 04 = 58; 05 = 27.
SELECT version_id, count(*) AS notices
FROM notice GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
