-- Data-integrity guard: business metrics can never be negative.
select song_id, distinct_isrc_count as bad_value
from {{ ref('mart_song_spotify_isrc_counts') }}
where distinct_isrc_count < 0

union all

select song_id, youtube_video_count as bad_value
from {{ ref('mart_song_youtube_video_counts') }}
where youtube_video_count < 0
