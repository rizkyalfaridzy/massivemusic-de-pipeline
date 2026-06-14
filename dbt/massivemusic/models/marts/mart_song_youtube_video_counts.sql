-- BUSINESS QUESTION 2:
-- "How many videos each song has in YouTube."
-- Count DISTINCT videos matched to a song.
select
    d.song_id,
    d.song_title,
    d.artist_name,
    count(distinct v.video_id) as youtube_video_count
from {{ ref('dim_song') }} d
left join {{ ref('fct_youtube_videos') }} v on v.song_id = d.song_id
group by 1, 2, 3
