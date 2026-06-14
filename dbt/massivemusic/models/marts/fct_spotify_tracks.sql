-- fct_spotify_tracks: track-level grain, joined to the song dimension.
select
    t.spotify_track_id,
    t.song_id,
    t.isrc,
    t.is_valid_isrc,
    t.track_name,
    t.album_name,
    t.artist_name,
    t.popularity,
    t.duration_ms,
    t.spotify_url
from {{ ref('stg_spotify_tracks') }} t
inner join {{ ref('dim_song') }} d on d.song_id = t.song_id
