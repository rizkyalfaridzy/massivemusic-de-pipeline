-- Clean & standardize the internal catalog.
-- Dedup defensively on song_id (the sheet may contain accidental duplicates).
with source as (
    select * from {{ source('raw', 'catalog') }}
),

cleaned as (
    select
        trim(song_id)                                   as song_id,
        initcap(trim(song_title))                       as song_title,
        nullif(initcap(trim(coalesce(artist_name, ''))), '') as artist_name,
        nullif(trim(coalesce(album, '')), '')           as album,
        nullif(upper(trim(coalesce(isrc, ''))), '')     as catalog_isrc,
        nullif(trim(coalesce(release_date, '')), '')    as release_date,
        _ingested_at
    from source
    where coalesce(trim(song_title), '') <> ''
),

deduped as (
    select *,
        row_number() over (
            partition by song_id order by _ingested_at desc
        ) as rn
    from cleaned
)

select song_id, song_title, artist_name, album, catalog_isrc, release_date
from deduped
where rn = 1
