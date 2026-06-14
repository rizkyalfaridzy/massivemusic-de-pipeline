-- fct_youtube_videos: video-level grain, joined to the song dimension.
select
    v.video_id,
    v.song_id,
    v.channel_id,
    v.channel_title,
    v.video_title,
    v.published_at,
    v.video_url
from {{ ref('stg_youtube_videos') }} v
inner join {{ ref('dim_song') }} d on d.song_id = v.song_id
