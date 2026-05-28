import os
import re
from typing import List, Optional, Tuple

import musicbrainzngs

musicbrainzngs.set_useragent("vinylstudio-to-jb7", "1.0")

TRACK_NUM_RE = re.compile(r"^\d+\s+")


class AlbumMetadata:
    __slots__ = ("artist", "title", "year", "genre", "tracks", "is_various")

    def __init__(
        self,
        artist: str = "",
        title: str = "",
        year: str = "1970",
        genre: str = "Unknown",
        tracks: Optional[List[str]] = None,
        is_various: bool = False,
    ):
        self.artist = artist
        self.title = title
        self.year = year
        self.genre = genre
        self.tracks = tracks or []
        self.is_various = is_various


def strip_track_number(filename: str) -> str:
    return TRACK_NUM_RE.sub("", filename, count=1)


def parse_album_dir(dirname: str) -> Tuple[str, str]:
    parts = re.split(r" {2,}", dirname.strip(), maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return dirname.strip(), dirname.strip()


def lookup_album_metadata(artist: str, album_title: str) -> Optional[AlbumMetadata]:
    try:
        result = musicbrainzngs.search_releases(
            artist=artist, release=album_title, limit=5
        )
        releases = result.get("release-list", [])
        if not releases:
            return None

        album_lower = album_title.lower().strip()
        best = None
        for r in releases:
            title = r.get("title", "").lower().strip()
            if title == album_lower:
                best = r
                break
            if best is None and (album_lower in title or title in album_lower):
                best = r

        if best is None:
            best = releases[0]

        return _parse_release(best)
    except Exception:
        return None


def search_releases(artist: str, album: str, limit: int = 10) -> List[dict]:
    """Search MusicBrainz for releases matching artist + album. Returns list of {id, title, year, artist, format, track_count}."""
    try:
        result = musicbrainzngs.search_releases(
            artist=artist, release=album, limit=limit
        )
        candidates = []
        for r in result.get("release-list", []):
            date = r.get("date", "")
            year = date[:4] if date and len(date) >= 4 else ""
            artist_name = ""
            ac = r.get("artist-credit", [])
            if ac and isinstance(ac[0], dict):
                artist_name = ac[0].get("name", "")

            medium_list = r.get("medium-list", [])
            formats = []
            total_tracks = 0
            for m in medium_list:
                fmt = m.get("format", "")
                if fmt:
                    formats.append(fmt)
                try:
                    total_tracks += int(m.get("track-count", 0) or 0)
                except (ValueError, TypeError):
                    pass
            format_str = "/".join(dict.fromkeys(formats)) if formats else ""

            candidates.append({
                "id": r["id"],
                "title": r.get("title", ""),
                "year": year,
                "artist": artist_name,
                "format": format_str,
                "track_count": total_tracks,
            })
        return candidates
    except Exception:
        return []


def search_artists(query: str) -> List[dict]:
    try:
        result = musicbrainzngs.search_artists(artist=query, limit=20)
        return [
            {
                "id": a["id"],
                "name": a["name"],
                "disambiguation": a.get("disambiguation", ""),
            }
            for a in result.get("artist-list", [])
        ]
    except Exception:
        return []


def get_artist_releases(artist_id: str) -> List[dict]:
    try:
        result = musicbrainzngs.browse_releases(
            artist=artist_id, release_type="album", limit=100,
            includes=["media"],
        )
        releases = []
        for r in result.get("release-list", []):
            date = r.get("date", "")
            year = date[:4] if date and len(date) >= 4 else ""

            medium_list = r.get("medium-list", [])
            formats = []
            total_tracks = 0
            for m in medium_list:
                fmt = m.get("format", "")
                if fmt:
                    formats.append(fmt)
                try:
                    total_tracks += int(m.get("track-count", 0) or 0)
                except (ValueError, TypeError):
                    pass
            format_str = "/".join(dict.fromkeys(formats)) if formats else ""

            releases.append({
                "id": r["id"],
                "title": r.get("title", ""),
                "year": year,
                "format": format_str,
                "track_count": total_tracks,
            })
        return releases
    except Exception:
        return []


def get_release_metadata(release_id: str) -> Optional[AlbumMetadata]:
    try:
        detail = musicbrainzngs.get_release_by_id(
            release_id, includes=["recordings", "tags", "release-groups"]
        )
        release = detail.get("release", {})
        return _parse_release(release)
    except Exception:
        return None


def _parse_release(release: dict) -> AlbumMetadata:
    artist_credit = release.get("artist-credit", [])
    artist_name = ""
    if artist_credit and isinstance(artist_credit[0], dict):
        artist_name = artist_credit[0].get("name", "")

    title = release.get("title", "")
    date = release.get("date", "")
    year = date[:4] if date and len(date) >= 4 else "1970"

    meta = AlbumMetadata(
        artist=artist_name,
        title=title,
        year=year,
        is_various=(artist_name.lower() == "various artists"),
    )

    release_id = release.get("id")
    if release_id:
        try:
            detail = musicbrainzngs.get_release_by_id(
                release_id, includes=["recordings", "tags", "release-groups"]
            )
            r = detail.get("release", {})
            _populate_tracks(r, meta)
            _populate_genre(r, meta)
            _check_various_artists(r, meta)
        except Exception:
            pass

    return meta


def _populate_tracks(release: dict, meta: AlbumMetadata) -> None:
    medium_list = release.get("medium-list", [])
    tracks: List[str] = []
    track_artists: set = set()

    for medium in medium_list:
        track_list = medium.get("track-list", [])
        for track in track_list:
            recording = track.get("recording", track)
            track_title = recording.get("title", "")
            if not track_title:
                continue

            ta_credit = recording.get("artist-credit", [])
            has_track_artist = False
            if ta_credit and isinstance(ta_credit[0], dict):
                ta_name = ta_credit[0].get("name", "")
                if ta_name and ta_name != meta.artist:
                    track_artists.add(ta_name)
                    tracks.append(f"{ta_name} / {track_title}")
                    has_track_artist = True

            if not has_track_artist:
                tracks.append(track_title)

    meta.tracks = tracks
    if len(track_artists) > 1 or (
        track_artists and meta.artist.lower() == "various artists"
    ):
        meta.is_various = True


def _populate_genre(release: dict, meta: AlbumMetadata) -> None:
    tag_counts: dict = {}

    rg = release.get("release-group", {})
    for tg in rg.get("tag-list", []):
        if isinstance(tg, dict):
            name = tg.get("name", "")
            count = int(tg.get("count", 0) or 0)
            tag_counts[name] = count

    if not tag_counts:
        for tg in release.get("tag-list", []):
            if isinstance(tg, dict):
                name = tg.get("name", "")
                count = int(tg.get("count", 0) or 0)
                tag_counts[name] = count

    skip_tags = {
        "various",
        "misc",
        "various artists",
        "album",
        "compilation",
        "soundtrack",
        "live",
        "remix",
        "bootleg",
    }
    genre_tags = {
        k: v for k, v in tag_counts.items() if k.lower() not in skip_tags and k.isascii()
    }

    if genre_tags:
        best = max(genre_tags, key=genre_tags.get)
        meta.genre = best.capitalize()


def _check_various_artists(release: dict, meta: AlbumMetadata) -> None:
    medium_list = release.get("medium-list", [])
    artists: set = set()
    for medium in medium_list:
        track_list = medium.get("track-list", [])
        for track in track_list:
            recording = track.get("recording", track)
            ta_credit = recording.get("artist-credit", [])
            if ta_credit and isinstance(ta_credit[0], dict):
                artists.add(ta_credit[0].get("name", ""))
    if len(artists) > 1:
        meta.is_various = True


def generate_id_file(
    album_dir: str, metadata: AlbumMetadata, stripped_filenames: List[str]
) -> str:
    id_path = os.path.join(album_dir, "id")

    lines: List[str] = []
    if metadata.is_various:
        title = metadata.title or os.path.basename(os.path.normpath(album_dir))
        lines.append(f"Various Artists / {title}")
    elif metadata.artist and metadata.title:
        lines.append(f"{metadata.artist} / {metadata.title}")
    else:
        lines.append(os.path.basename(os.path.normpath(album_dir)))

    lines.append(metadata.year)
    lines.append(metadata.genre)

    if metadata.tracks:
        lines.extend(metadata.tracks)
    else:
        for f in stripped_filenames:
            name = os.path.splitext(f)[0]
            if name:
                lines.append(name)

    while lines and not lines[-1].strip():
        lines.pop()

    content = "\n".join(lines) + "\n"
    with open(id_path, "w", encoding="utf-8") as f:
        f.write(content)

    return id_path


AUDIO_EXTS = frozenset({".mp3", ".flac", ".wav", ".wma", ".ogg", ".m4a", ".aac", ".ape"})


def get_track_files(album_dir: str) -> List[str]:
    files = []
    try:
        for f in sorted(os.listdir(album_dir)):
            if os.path.isfile(os.path.join(album_dir, f)):
                ext = os.path.splitext(f)[1].lower()
                if ext in AUDIO_EXTS:
                    files.append(f)
    except PermissionError:
        pass
    return files
