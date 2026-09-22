-- SPDX-License-Identifier: AGPL-3.0-only
--
-- F1 base rate, per population band. The query crony-eu/docs/flags/F1-same-body.md
-- cites, and the only place these numbers are computed.
--
-- Unit: distinct (commune, supplier) pairs. Every count below counts pairs, never
-- contracts and never hit rows: a supplier with forty contracts to one commune is
-- one pair, and a framework agreement invoiced monthly is not forty relationships.
--
-- A pair is:
--   in the denominator   when it has a contract meeting conditions 1 to 3
--   a candidate pair     when at least one hit links it (judgment pending or confirmed)
--   a confirmed pair     when at least one of its hits carries a confirmed judgment
--   packet-eligible      when at least one of its hits passes every gate
--
-- A gate "removes" a candidate pair when none of the pair's hits passes it. Losses
-- are counted per gate and never netted, so one pair can appear under several
-- gates, which is the point: the table shows which gate is binding.
--
-- Parameters: $hits and $pairs, the flag run's hits.parquet and pairs.parquet.

WITH pair AS (
    SELECT commune_code, supplier_siren, population_band
    FROM read_parquet($pairs)
),
per_pair AS (
    SELECT
        commune_code,
        supplier_siren,
        bool_or(judgment_status = 'confirmed')      AS confirmed,
        bool_or(packet_eligible)                    AS eligible,
        bool_or(role_overlap <> 'unknown')          AS role_resolved,
        bool_or(gate_buyer_verified)                AS buyer_verified,
        bool_or(historical_geography = 'not_established') AS geography_not_established,
        bool_or(gate_judgment_confirmed)            AS passes_judgment,
        bool_or(gate_mandate_overlap)               AS passes_mandate,
        bool_or(gate_role_overlap)                  AS passes_role,
        bool_or(gate_redistributable)               AS passes_redistributable,
        bool_or(buyer_identity_corroborated = 'true') AS passes_buyer_identity,
        bool_or(historical_geography <> 'contradicted') AS passes_geography,
        bool_or(gate_calibrated)                    AS passes_calibration
    FROM read_parquet($hits)
    GROUP BY commune_code, supplier_siren
)
SELECT
    p.population_band                                             AS band,
    count(*)                                                      AS pairs,
    count(h.commune_code)                                         AS candidate_pairs,
    count(*) FILTER (h.confirmed)                                 AS confirmed_pairs,
    count(*) FILTER (h.eligible)                                  AS eligible_pairs,
    count(*) FILTER (h.role_resolved)                             AS role_resolved_pairs,
    count(*) FILTER (h.buyer_verified)                            AS buyer_verified_pairs,
    count(*) FILTER (h.geography_not_established)                 AS geography_not_established_pairs,
    count(*) FILTER (h.commune_code IS NOT NULL AND NOT h.passes_judgment)        AS lost_judgment_not_confirmed,
    count(*) FILTER (h.commune_code IS NOT NULL AND NOT h.passes_mandate)         AS lost_mandate_overlap_unknown,
    -- The spec calls this line "role overlap unknown". It counts pairs with no hit
    -- whose role overlap is true, which is unknown or false; from the company
    -- API every role date is absent, so today it is all unknown.
    count(*) FILTER (h.commune_code IS NOT NULL AND NOT h.passes_role)            AS lost_role_overlap_not_true,
    count(*) FILTER (h.commune_code IS NOT NULL AND NOT h.passes_redistributable) AS lost_not_redistributable,
    count(*) FILTER (h.commune_code IS NOT NULL AND NOT h.passes_buyer_identity)  AS lost_buyer_not_corroborated,
    count(*) FILTER (h.commune_code IS NOT NULL AND NOT h.passes_geography)       AS lost_buyer_contradicted,
    count(*) FILTER (h.commune_code IS NOT NULL AND NOT h.passes_calibration)     AS lost_uncalibrated
FROM pair p
LEFT JOIN per_pair h USING (commune_code, supplier_siren)
GROUP BY p.population_band
ORDER BY p.population_band
