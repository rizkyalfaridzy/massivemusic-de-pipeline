-- dim_song: the conformed song dimension, one row per internal catalog song.
select
    song_id,
    song_title,
    artist_name,
    album,
    catalog_isrc,
    release_date
from {{ ref('stg_catalog') }}
