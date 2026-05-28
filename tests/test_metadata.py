import os

import pytest

from vinylstudio_to_jb7.metadata import (
    AUDIO_EXTS,
    AlbumMetadata,
    _check_various_artists,
    _populate_genre,
    _populate_tracks,
    generate_id_file,
    get_artist_releases,
    get_release_metadata,
    get_track_files,
    lookup_album_metadata,
    parse_album_dir,
    search_artists,
    search_releases,
    strip_track_number,
)


class TestStripTrackNumber:
    def test_leading_digit_space(self):
        assert strip_track_number("01 White Flag.mp3") == "White Flag.mp3"

    def test_leading_digit_multi(self):
        assert strip_track_number("10 Stoned.mp3") == "Stoned.mp3"

    def test_no_track_number(self):
        assert strip_track_number("White Flag.mp3") == "White Flag.mp3"

    def test_multi_digit(self):
        assert strip_track_number("123 Song.mp3") == "Song.mp3"

    def test_leading_zeroes(self):
        assert strip_track_number("001 Track.mp3") == "Track.mp3"


class TestParseAlbumDir:
    def test_three_spaces(self):
        assert parse_album_dir("Dido   Life For Rent") == ("Dido", "Life For Rent")

    def test_two_spaces(self):
        assert parse_album_dir("Dido  Life For Rent") == ("Dido", "Life For Rent")

    def test_no_separator(self):
        assert parse_album_dir("AlbumOnly") == ("AlbumOnly", "AlbumOnly")

    def test_leading_trailing_spaces(self):
        assert parse_album_dir("  Dido   Life For Rent  ") == ("Dido", "Life For Rent")

    def test_multi_word_artist(self):
        assert parse_album_dir("Pink Floyd   Dark Side") == ("Pink Floyd", "Dark Side")


class TestAlbumMetadata:
    def test_defaults(self):
        m = AlbumMetadata()
        assert m.artist == ""
        assert m.title == ""
        assert m.year == "1970"
        assert m.genre == "Unknown"
        assert m.tracks == []
        assert m.is_various is False

    def test_full_init(self):
        m = AlbumMetadata(
            artist="Dido",
            title="Life For Rent",
            year="2003",
            genre="Alternative Rock",
            tracks=["White Flag", "Stoned"],
            is_various=False,
        )
        assert m.artist == "Dido"
        assert m.title == "Life For Rent"


class TestGenerateIdFile:
    def test_basic(self, tmp_path):
        meta = AlbumMetadata(
            artist="Dido",
            title="Life For Rent",
            year="2003",
            genre="Alternative Rock",
            tracks=["White Flag", "Stoned"],
        )
        path = generate_id_file(str(tmp_path), meta, [])
        with open(path) as f:
            content = f.read()
        assert content == "Dido / Life For Rent\n2003\nAlternative Rock\nWhite Flag\nStoned\n"

    def test_uses_filenames_when_no_tracks(self, tmp_path):
        meta = AlbumMetadata(artist="Dido", title="Life For Rent")
        path = generate_id_file(str(tmp_path), meta, ["White Flag.mp3", "Stoned.mp3"])
        with open(path) as f:
            content = f.read()
        assert "White Flag" in content
        assert "Stoned" in content
        assert ".mp3" not in content

    def test_various_artists(self, tmp_path):
        meta = AlbumMetadata(
            artist="Various Artists",
            title="Compilation",
            is_various=True,
            tracks=["Artist1 / Song A", "Artist2 / Song B"],
        )
        path = generate_id_file(str(tmp_path), meta, [])
        with open(path) as f:
            content = f.read()
        assert content.startswith("Various Artists / Compilation")
        assert "Artist1 / Song A" in content

    def test_empty_artist_uses_dirname(self, tmp_path):
        meta = AlbumMetadata(title="MyAlbum")
        path = generate_id_file(str(tmp_path), meta, [])
        with open(path) as f:
            content = f.read()
        dirname = os.path.basename(str(tmp_path))
        assert content.startswith(dirname)


class TestPopulateTracks:
    def test_simple_tracks(self):
        release = {
            "medium-list": [
                {
                    "track-list": [
                        {"recording": {"title": "Song A"}},
                        {"recording": {"title": "Song B"}},
                    ]
                }
            ]
        }
        meta = AlbumMetadata(artist="Artist")
        _populate_tracks(release, meta)
        assert meta.tracks == ["Song A", "Song B"]

    def test_various_artists_tracks(self):
        release = {
            "medium-list": [
                {
                    "track-list": [
                        {
                            "recording": {
                                "title": "Song A",
                                "artist-credit": [{"name": "Artist1"}],
                            }
                        },
                        {
                            "recording": {
                                "title": "Song B",
                                "artist-credit": [{"name": "Artist2"}],
                            }
                        },
                    ]
                }
            ]
        }
        meta = AlbumMetadata(artist="Various Artists")
        _populate_tracks(release, meta)
        assert "Artist1 / Song A" in meta.tracks
        assert "Artist2 / Song B" in meta.tracks
        assert meta.is_various is True

    def test_track_with_same_artist_not_prefixed(self):
        release = {
            "medium-list": [
                {
                    "track-list": [
                        {
                            "recording": {
                                "title": "Song A",
                                "artist-credit": [{"name": "Dido"}],
                            }
                        },
                    ]
                }
            ]
        }
        meta = AlbumMetadata(artist="Dido")
        _populate_tracks(release, meta)
        assert meta.tracks == ["Song A"]

    def test_handles_no_recording_key(self):
        release = {
            "medium-list": [
                {
                    "track-list": [
                        {"title": "Track 1"},
                        {"title": "Track 2"},
                    ]
                }
            ]
        }
        meta = AlbumMetadata(artist="Artist")
        _populate_tracks(release, meta)
        assert meta.tracks == ["Track 1", "Track 2"]


class TestPopulateGenre:
    def test_from_release_group(self):
        release = {
            "release-group": {
                "tag-list": [{"name": "rock", "count": 5}, {"name": "album", "count": 3}]
            }
        }
        meta = AlbumMetadata()
        _populate_genre(release, meta)
        assert meta.genre == "Rock"

    def test_skip_non_genre_tags(self):
        release = {
            "release-group": {
                "tag-list": [
                    {"name": "compilation", "count": 10},
                    {"name": "various", "count": 5},
                ]
            }
        }
        meta = AlbumMetadata()
        _populate_genre(release, meta)
        assert meta.genre == "Unknown"

    def test_remains_unknown_when_no_tags(self):
        release = {"release-group": {}}
        meta = AlbumMetadata()
        _populate_genre(release, meta)
        assert meta.genre == "Unknown"


class TestCheckVariousArtists:
    def test_multiple_artists(self):
        release = {
            "medium-list": [
                {
                    "track-list": [
                        {"recording": {"artist-credit": [{"name": "A"}]}},
                        {"recording": {"artist-credit": [{"name": "B"}]}},
                    ]
                }
            ]
        }
        meta = AlbumMetadata(artist="Compilation")
        _check_various_artists(release, meta)
        assert meta.is_various is True

    def test_same_artist(self):
        release = {
            "medium-list": [
                {
                    "track-list": [
                        {"recording": {"artist-credit": [{"name": "Dido"}]}},
                        {"recording": {"artist-credit": [{"name": "Dido"}]}},
                    ]
                }
            ]
        }
        meta = AlbumMetadata(artist="Dido")
        _check_various_artists(release, meta)
        assert meta.is_various is False


class TestGetTrackFiles:
    def test_returns_audio_files(self, tmp_path):
        (tmp_path / "track1.mp3").write_text("x")
        (tmp_path / "track2.flac").write_text("x")
        (tmp_path / "cover.jpg").write_text("x")
        (tmp_path / "id").write_text("x")
        files = get_track_files(str(tmp_path))
        assert "track1.mp3" in files
        assert "track2.flac" in files
        assert "cover.jpg" not in files

    def test_sorted_order(self, tmp_path):
        (tmp_path / "z.mp3").write_text("x")
        (tmp_path / "a.mp3").write_text("x")
        files = get_track_files(str(tmp_path))
        assert files == ["a.mp3", "z.mp3"]

    def test_empty_dir(self, tmp_path):
        assert get_track_files(str(tmp_path)) == []


class TestLookupAlbumMetadata:
    def test_returns_none_on_failure(self, monkeypatch):
        def mock_search(**kwargs):
            return {"release-list": []}

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.search_releases", mock_search
        )
        result = lookup_album_metadata("Nonexistent", "Nothing")
        assert result is None

    def test_returns_metadata_on_success(self, monkeypatch):
        def mock_search(**kwargs):
            return {
                "release-list": [
                    {
                        "id": "abc123",
                        "title": "Life For Rent",
                        "artist-credit": [{"name": "Dido"}],
                        "date": "2003-09-29",
                    }
                ]
            }

        def mock_get_by_id(*args, **kwargs):
            return {
                "release": {
                    "id": "abc123",
                    "title": "Life For Rent",
                    "artist-credit": [{"name": "Dido"}],
                    "date": "2003-09-29",
                    "medium-list": [
                        {
                            "track-list": [
                                {"recording": {"title": "White Flag"}},
                                {"recording": {"title": "Stoned"}},
                            ]
                        }
                    ],
                    "release-group": {
                        "tag-list": [{"name": "alternative", "count": 3}]
                    },
                }
            }

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.search_releases", mock_search
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.get_release_by_id",
            mock_get_by_id,
        )
        result = lookup_album_metadata("Dido", "Life For Rent")
        assert result is not None
        assert result.artist == "Dido"
        assert result.title == "Life For Rent"
        assert result.year == "2003"
        assert result.genre == "Alternative"
        assert "White Flag" in result.tracks

    def test_exact_title_match_preferred(self, monkeypatch):
        calls = []

        def mock_search(**kwargs):
            calls.append((kwargs.get("artist"), kwargs.get("release")))
            return {
                "release-list": [
                    {"id": "2", "title": "Life", "artist-credit": [{"name": "Dido"}], "date": "2003"},
                    {
                        "id": "1",
                        "title": "Life For Rent",
                        "artist-credit": [{"name": "Dido"}],
                        "date": "2003",
                    },
                ]
            }

        def mock_get_by_id(**kwargs):
            rid = kwargs.get("id")
            return {
                "release": {
                    "id": rid,
                    "title": "Life For Rent" if rid == "1" else "Life",
                    "artist-credit": [{"name": "Dido"}],
                    "date": "2003",
                    "medium-list": [],
                    "release-group": {},
                }
            }

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.search_releases", mock_search
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.get_release_by_id",
            mock_get_by_id,
        )
        result = lookup_album_metadata("Dido", "Life For Rent")
        assert result is not None
        assert result.title == "Life For Rent"


class TestSearchArtists:
    def test_returns_list(self, monkeypatch):
        def mock_search(**kwargs):
            return {
                "artist-list": [
                    {"id": "1", "name": "Dido", "disambiguation": ""},
                    {"id": "2", "name": "Dido (singer)", "disambiguation": "singer"},
                ]
            }

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.search_artists", mock_search
        )
        results = search_artists("Dido")
        assert len(results) == 2
        assert results[0]["name"] == "Dido"
        assert results[1]["name"] == "Dido (singer)"

    def test_returns_empty_on_exception(self, monkeypatch):
        def mock_search(**kwargs):
            raise Exception("API error")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.search_artists", mock_search
        )
        results = search_artists("Dido")
        assert results == []


class TestGetArtistReleases:
    def test_returns_releases(self, monkeypatch):
        def mock_browse(**kwargs):
            return {
                "release-list": [
                    {
                        "id": "1", "title": "Album 1", "date": "2000",
                        "medium-list": [
                            {"format": "CD", "track-count": "10"},
                            {"format": "DVD", "track-count": "5"},
                        ],
                    },
                    {
                        "id": "2", "title": "Album 2", "date": "",
                        "medium-list": [{"format": "Vinyl", "track-count": "8"}],
                    },
                ]
            }

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.browse_releases", mock_browse
        )
        releases = get_artist_releases("artist-id")
        assert len(releases) == 2
        assert releases[0]["title"] == "Album 1"
        assert releases[0]["year"] == "2000"
        assert releases[0]["format"] == "CD/DVD"
        assert releases[0]["track_count"] == 15
        assert releases[1]["format"] == "Vinyl"
        assert releases[1]["track_count"] == 8

    def test_returns_empty_on_exception(self, monkeypatch):
        def mock_browse(**kwargs):
            raise Exception("error")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.browse_releases", mock_browse
        )
        assert get_artist_releases("bad-id") == []


class TestSearchReleases:
    def test_returns_candidates(self, monkeypatch):
        def mock_search(**kwargs):
            return {
                "release-list": [
                    {"id": "1", "title": "Album", "artist-credit": [{"name": "Artist"}], "date": "2000"},
                    {"id": "2", "title": "Album", "artist-credit": [{"name": "Artist"}], "date": "2010"},
                ]
            }

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.search_releases", mock_search
        )
        results = search_releases("Artist", "Album")
        assert len(results) == 2
        assert results[0]["year"] == "2000"
        assert results[1]["year"] == "2010"

    def test_returns_empty_on_exception(self, monkeypatch):
        def mock_search(**kwargs):
            raise Exception("error")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.search_releases", mock_search
        )
        assert search_releases("Artist", "Album") == []


class TestGetReleaseMetadata:
    def test_returns_metadata(self, monkeypatch):
        def mock_get(*args, **kwargs):
            return {
                "release": {
                    "id": "abc",
                    "title": "Test",
                    "artist-credit": [{"name": "Artist"}],
                    "date": "2010",
                    "medium-list": [],
                    "release-group": {},
                }
            }

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.get_release_by_id", mock_get
        )
        meta = get_release_metadata("abc")
        assert meta is not None
        assert meta.artist == "Artist"
        assert meta.title == "Test"

    def test_returns_none_on_exception(self, monkeypatch):
        def mock_get(**kwargs):
            raise Exception("error")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.metadata.musicbrainzngs.get_release_by_id", mock_get
        )
        assert get_release_metadata("bad") is None
