-- Detect malformed ISRCs that slipped through (anomaly detection).
-- A non-null ISRC marked invalid is a data-quality anomaly worth surfacing.
select spotify_track_id, isrc
from {{ ref('stg_spotify_tracks') }}
where isrc is not null
  and is_valid_isrc = false
