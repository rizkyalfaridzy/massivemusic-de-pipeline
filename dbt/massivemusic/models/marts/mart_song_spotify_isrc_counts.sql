-- BUSINESS QUESTION 1:
-- "How many ISRC(s) are in each song in Spotify."
-- Count DISTINCT valid ISRCs found across all Spotify tracks matched to a song.
select
    d.song_id,
    d.song_title,
    d.artist_name,
    count(distinct case when t.is_valid_isrc then t.isrc end) as distinct_isrc_count,
    count(t.spotify_track_id)                                 as matched_track_count
from {{ ref('dim_song') }} d
left join {{ ref('fct_spotify_tracks') }} t on t.song_id = d.song_id
group by 1, 2, 3
