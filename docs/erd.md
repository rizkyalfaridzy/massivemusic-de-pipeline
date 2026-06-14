# Entity Relationship Diagram

The warehouse follows a **medallion** layout: `raw` (landing) → `staging`
(cleaned views) → `marts` (dimensional model + business answers). The diagram
below shows the modeled layer (`marts`). A rendered PNG is at
[`erd.png`](./erd.png).

```mermaid
erDiagram
    dim_song ||--o{ fct_spotify_tracks : "has tracks"
    dim_song ||--o{ fct_youtube_videos : "has videos"
    dim_song ||--|| mart_song_spotify_isrc_counts : "aggregates"
    dim_song ||--|| mart_song_youtube_video_counts : "aggregates"
    dim_song ||--|| mart_song_overview : "aggregates"

    dim_song {
        text song_id PK
        text song_title
        text artist_name
        text album
        text catalog_isrc
        text release_date
    }

    fct_spotify_tracks {
        text spotify_track_id PK
        text song_id FK
        text isrc
        bool is_valid_isrc
        text track_name
        int  popularity
        int  duration_ms
    }

    fct_youtube_videos {
        text video_id PK
        text song_id FK
        text channel_id
        text channel_title
        text video_title
        text published_at
    }

    mart_song_spotify_isrc_counts {
        text song_id PK
        text song_title
        int  distinct_isrc_count
        int  matched_track_count
    }

    mart_song_youtube_video_counts {
        text song_id PK
        text song_title
        int  youtube_video_count
    }

    mart_song_overview {
        text song_id PK
        text song_title
        int  spotify_distinct_isrc_count
        int  youtube_video_count
    }
```

## Grain & keys

| Table | Grain | Primary key |
|-------|-------|-------------|
| `dim_song` | one internal song | `song_id` |
| `fct_spotify_tracks` | one Spotify track matched to a song | `spotify_track_id` |
| `fct_youtube_videos` | one YouTube video matched to a song | `video_id` |
| `mart_song_spotify_isrc_counts` | one song | `song_id` |
| `mart_song_youtube_video_counts` | one song | `song_id` |
| `mart_song_overview` | one song | `song_id` |

The two business questions are answered directly by the two count marts;
`mart_song_overview` joins them for BI convenience.
