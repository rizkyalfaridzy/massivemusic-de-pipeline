-- Convenience mart combining both business answers in one row per song,
-- ready for BI tools / dashboards.
select
    d.song_id,
    d.song_title,
    d.artist_name,
    coalesce(s.distinct_isrc_count, 0)   as spotify_distinct_isrc_count,
    coalesce(s.matched_track_count, 0)   as spotify_matched_track_count,
    coalesce(y.youtube_video_count, 0)   as youtube_video_count
from {{ ref('dim_song') }} d
left join {{ ref('mart_song_spotify_isrc_counts') }} s on s.song_id = d.song_id
left join {{ ref('mart_song_youtube_video_counts') }} y on y.song_id = d.song_id
