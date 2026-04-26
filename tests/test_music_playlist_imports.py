"""Layer 2: Import validation for music playlist modules."""


class TestMusicPlaylistImports:
    def test_music_playlist_service_import(self):
        from src.services.music_playlist_service import MusicPlaylistService

        assert MusicPlaylistService is not None

    def test_all_playlist_exports_are_reachable(self):
        from src.services.music_playlist_service import (
            MusicPlaylistService,
            PlaylistState,
            SongDict,
            get_music_playlist_service,
        )

        assert callable(get_music_playlist_service)
        assert MusicPlaylistService is not None
        assert SongDict is not None
        assert PlaylistState is not None
