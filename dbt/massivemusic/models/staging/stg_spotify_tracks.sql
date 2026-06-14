-- Standardize Spotify tracks. Dedup on spotify_track_id. Flag malformed ISRCs.
-- ISRC format: 2-letter country + 3 alphanumeric registrant + 2-digit year + 5-digit code.
with source as (
    select * from {{ source('raw', 'spotify_tracks') }}
),

cleaned as (
    select
        trim(song_id)                                       as song_id,
        trim(spotify_track_id)                              as spotify_track_id,
        nullif(upper(trim(coalesce(isrc, ''))), '')         as isrc,
        trim(track_name)                                    as track_name,
        nullif(trim(coalesce(album_name, '')), '')          as album_name,
        nullif(trim(coalesce(release_date, '')), '')        as release_date,
        trim(artist_name)                                   as artist_name,
        {{ try_cast_int('popularity') }}                    as popularity,
        {{ try_cast_int('duration_ms') }}                   as duration_ms,
        spotify_url,
        _ingested_at
    from source
    where coalesce(trim(spotify_track_id), '') <> ''
),

flagged as (
    select *,
        case
            when isrc is null then false
            when isrc ~ '^[A-Z]{2}[A-Z0-9]{3}[0-9]{2}[0-9]{5}$' then true
            else false
        end as is_valid_isrc
    from cleaned
),

deduped as (
    select *,
        row_number() over (
            partition by spotify_track_id order by _ingested_at desc
        ) as rn
    from flagged
)

select
    song_id, spotify_track_id, isrc, is_valid_isrc, track_name,
    album_name, release_date, artist_name, popularity, duration_ms, spotify_url
from deduped
where rn = 1
