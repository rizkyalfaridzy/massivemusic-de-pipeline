-- Standardize YouTube videos. Dedup on (song_id, video_id): the same video can
-- legitimately appear for one song, but never twice for the same song.
with source as (
    select * from {{ source('raw', 'youtube_videos') }}
),

cleaned as (
    select
        trim(song_id)                                   as song_id,
        trim(video_id)                                  as video_id,
        trim(channel_id)                                as channel_id,
        nullif(trim(coalesce(channel_title, '')), '')   as channel_title,
        nullif(trim(coalesce(video_title, '')), '')     as video_title,
        nullif(trim(coalesce(published_at, '')), '')    as published_at,
        video_url,
        _ingested_at
    from source
    where coalesce(trim(video_id), '') <> ''
),

deduped as (
    select *,
        row_number() over (
            partition by song_id, video_id order by _ingested_at desc
        ) as rn
    from cleaned
)

select song_id, video_id, channel_id, channel_title, video_title, published_at, video_url
from deduped
where rn = 1
