"""Music API router for story-based music recommendation."""

import asyncio
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from src.api.deps import get_current_user_optional
from src.database.models import SessionLocal
from src.services.minimax_config import build_minimax_config
from src.services.music_playlist_service import get_music_playlist_service
from src.services.music_service import get_music_service

logger = logging.getLogger(__name__)

router = APIRouter()

# LRU 内存缓存：最多缓存 10 首歌的完整音频，避免重复下载
_audio_cache: OrderedDict[int, Tuple[bytes, str]] = OrderedDict()
_AUDIO_CACHE_MAX = 10
_audio_cache_lock = asyncio.Lock()


@dataclass(frozen=True)
class GeneratedMusicPayload:
    content: bytes
    media_type: str


def read_generated_music_file(
    file_name: str,
    asset_dir: Optional[Path] = None,
) -> Optional[GeneratedMusicPayload]:
    """Read a generated music asset without allowing path traversal."""
    allowed_suffixes = {".mp3": "audio/mpeg", ".wav": "audio/wav"}
    path = Path(file_name)
    if path.name != file_name or path.suffix not in allowed_suffixes:
        return None
    root = asset_dir or build_minimax_config().music_asset_dir
    candidate = (root / file_name).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents:
        return None
    if not candidate.is_file():
        return None
    return GeneratedMusicPayload(
        content=candidate.read_bytes(),
        media_type=allowed_suffixes[path.suffix],
    )


def _music_generation_failure_detail(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        message = re.sub(r"https?://\S+", "<url>", message)
        message = re.sub(r"(/[^\s'\"),]+)+", "<path>", message)
        message = message[:240]
        return f"AI music generation failed ({type(exc).__name__}: {message})"
    return f"AI music generation failed ({type(exc).__name__})"


class MusicRecommendationRequest(BaseModel):
    """音乐推荐请求"""

    story_text: str
    game_id: Optional[int] = None
    refresh: bool = False  # 刷新模式：复用缓存的 AI 分析，重新搜索歌曲
    character_settings: Optional[dict] = None  # 角色设定（含时代信息）


class SongResponse(BaseModel):
    """歌曲响应"""

    id: int
    name: str
    artists: List[str]
    album: str
    duration: int
    url: Optional[str] = None
    source: str = "netease"


class MusicRecommendationResponse(BaseModel):
    """音乐推荐响应"""

    keywords: List[str]
    mood: str
    scene_type: str
    environment: Optional[str] = None  # 环境氛围
    story_style: Optional[str] = None  # 故事风格
    music_style: Optional[str] = None  # 推荐音乐风格
    instruments: Optional[List[str]] = None  # 适合的乐器
    pacing: Optional[str] = None  # 叙事节奏
    time_weather: Optional[str] = None  # 时间天气
    description: Optional[str] = None  # 音乐氛围描述
    music_brief: Optional[dict] = None
    songs: List[SongResponse]


class PlaylistUpdateRequest(BaseModel):
    """Request body for updating a game playlist with new recommendation songs."""

    songs: List[SongResponse]
    mood: Optional[str] = None
    keywords: Optional[List[str]] = None


class PlaylistSyncRequest(BaseModel):
    """Request body for syncing playback state."""

    current_position_ms: int = 0
    is_playing: bool = False
    volume: float = 0.5


class MusicGenerationRequest(BaseModel):
    """Request body for story-conditioned generated music."""

    game_id: int
    story_text: str
    analysis: Dict[str, Any] = Field(default_factory=dict)


class MusicGenerationResponse(BaseModel):
    """Generated music result for frontend queue insertion."""

    track: Dict[str, Any]
    insert_policy: str


@router.post("/music/recommend", response_model=MusicRecommendationResponse)
async def recommend_music(
    request: MusicRecommendationRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """根据故事内容推荐音乐

    分析故事的情绪和场景，搜索匹配的音乐
    并批量获取所有歌曲的播放 URL
    """
    try:
        music_service = get_music_service()

        # 分析故事并获取推荐
        recommendation = await music_service.analyze_story_for_music(
            story_text=request.story_text,
            character_settings=request.character_settings,
            refresh=request.refresh,
        )

        # 批量获取所有歌曲的播放 URL（并行）
        import asyncio

        async def get_song_url_with_id(song):
            """获取歌曲 URL 并返回 (id, url)"""
            try:
                url = await music_service.get_song_play_url(song.id)
                return (song.id, url)
            except Exception as e:
                logger.warning(f"Failed to get URL for song {song.id}: {e}")
                return (song.id, None)

        # 并行获取所有歌曲的 URL
        url_tasks = [get_song_url_with_id(song) for song in recommendation.songs]
        url_results = await asyncio.gather(*url_tasks, return_exceptions=True)

        # 构建 URL 映射
        url_map = {}
        for result in url_results:
            if isinstance(result, tuple):
                song_id, url = result
                if url:
                    url_map[song_id] = url

        total_songs = len(recommendation.songs)
        available_songs = len(url_map)
        logger.info(f"[MusicAPI] Fetched {available_songs}/{total_songs} song URLs")

        # 过滤掉没有有效 URL 的歌曲
        filtered_out = [song for song in recommendation.songs if song.id not in url_map]
        if filtered_out:
            filtered_ids = [s.id for s in filtered_out]
            logger.info(
                f"[MusicAPI] Filtered out {len(filtered_out)} songs without URL: {filtered_ids}"
            )

        # ★ 如果可用歌曲过少，记录警告（帮助排查版权问题）
        if available_songs == 0 and total_songs > 0:
            logger.warning(
                f"[MusicAPI] All {total_songs} songs have no playable URL (copyright restrictions). "
                f"Keywords: {recommendation.keywords}"
            )
        elif available_songs < 3 and total_songs > 0:
            logger.warning(
                f"[MusicAPI] Only {available_songs}/{total_songs} songs available. "
                f"Consider adding more generic keywords. Keywords: {recommendation.keywords}"
            )

        # 转换为响应格式（只包含有 URL 的歌曲）
        songs = [
            SongResponse(
                id=song.id,
                name=song.name,
                artists=song.artists,
                album=song.album,
                duration=song.duration,
                url=url_map[song.id],
                source=song.source,
            )
            for song in recommendation.songs
            if song.id in url_map
        ]

        return MusicRecommendationResponse(
            keywords=recommendation.keywords,
            mood=recommendation.mood,
            scene_type=recommendation.scene_type,
            environment=recommendation.environment,
            story_style=recommendation.story_style,
            music_style=recommendation.music_style,
            instruments=recommendation.instruments,
            pacing=recommendation.pacing,
            time_weather=recommendation.time_weather,
            description=recommendation.description,
            music_brief=(
                recommendation.music_brief.to_analysis()
                if recommendation.music_brief is not None
                else None
            ),
            songs=songs,
        )

    except Exception as e:
        logger.exception(f"Failed to recommend music: {e}")
        raise HTTPException(status_code=500, detail=f"音乐推荐失败: {str(e)}")


@router.post("/music/generate", response_model=MusicGenerationResponse)
async def generate_music(request: MusicGenerationRequest):
    """Generate story-conditioned AI music without blocking recommendation search."""
    from src.services.minimax_music_generation import StoryMusicGenerationService

    config = build_minimax_config()
    if not config.music_generation_enabled:
        raise HTTPException(status_code=503, detail="AI music generation is disabled")

    db = SessionLocal()
    try:
        track = StoryMusicGenerationService().generate_ready_track(
            db=db,
            game_id=request.game_id,
            story_text=request.story_text,
            analysis=request.analysis,
        )
        get_music_playlist_service().insert_generated_track_for_game(
            db=db,
            game_id=request.game_id,
            generated_track=track,
        )
        return MusicGenerationResponse(track=track, insert_policy="future_queue")
    except RuntimeError as exc:
        logger.warning("[MusicAPI] Generated music unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("[MusicAPI] Generated music failed unexpectedly")
        raise HTTPException(status_code=503, detail=_music_generation_failure_detail(exc))
    finally:
        db.close()


@router.get("/music/song-url")
async def get_song_url(
    song_id: int = Query(..., description="歌曲ID"),
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """获取歌曲播放 URL

    注意：URL 有过期时间，需要时重新获取
    """
    try:
        music_service = get_music_service()
        url = await music_service.get_song_play_url(song_id)

        if not url:
            raise HTTPException(status_code=404, detail="无法获取歌曲播放地址")

        return {"url": url}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get song URL: {e}")
        raise HTTPException(status_code=500, detail=f"获取播放地址失败: {str(e)}")


@router.get("/music/search")
async def search_music(
    keyword: str = Query(..., min_length=1, max_length=50, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=30, description="返回数量"),
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """直接搜索音乐"""
    try:
        music_service = get_music_service()
        songs = await music_service.music_client.search(keyword, limit=limit)

        return {
            "songs": [
                SongResponse(
                    id=song.id,
                    name=song.name,
                    artists=song.artists,
                    album=song.album,
                    duration=song.duration,
                    url=song.url,
                    source=song.source,
                )
                for song in songs
            ]
        }

    except Exception as e:
        logger.exception(f"Failed to search music: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/music/generated/{file_name}")
async def get_generated_music(file_name: str) -> Response:
    """Serve provider-generated music assets from the configured asset directory."""
    generated_music = read_generated_music_file(file_name)
    if generated_music is None:
        raise HTTPException(status_code=404, detail="Generated music not found")
    return Response(
        content=generated_music.content,
        media_type=generated_music.media_type,
        headers={
            "content-length": str(len(generated_music.content)),
            "accept-ranges": "bytes",
            "cache-control": "public, max-age=300",
        },
    )


async def _get_or_download_audio(song_id: int, url: str) -> Tuple[bytes, str]:
    """下载完整音频到内存，带 LRU 缓存。MP3 通常 3-5MB，内存可接受。"""
    # 先检查缓存（短锁）
    async with _audio_cache_lock:
        if song_id in _audio_cache:
            _audio_cache.move_to_end(song_id)
            logger.info(f"[MusicStream] 缓存命中: song_id={song_id}")
            return _audio_cache[song_id]

    # 下载完整文件（不持锁）
    music_service = get_music_service()
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        cdn_headers = {"Referer": ""}
        response = await client.get(url, headers=cdn_headers)

        # URL 过期 → 刷新重试
        if response.status_code in (403, 401):
            logger.warning(
                f"[MusicStream] CDN 返回 {response.status_code} (URL可能过期): song_id={song_id}"
            )
            from src.services.music_service import NeteaseMusicClient

            if song_id in NeteaseMusicClient._url_cache:
                del NeteaseMusicClient._url_cache[song_id]
                logger.info(f"[MusicStream] URL刷新: 已清除 song_id={song_id} 的缓存")

            fresh_url = await music_service.get_song_play_url(song_id)
            if not fresh_url:
                raise HTTPException(status_code=404, detail="Song URL not available after refresh")
            logger.info(f"[MusicStream] URL刷新成功: song_id={song_id}")
            response = await client.get(fresh_url, headers={"Referer": ""})

        if response.status_code not in (200, 206):
            raise HTTPException(status_code=response.status_code, detail="CDN request failed")

        audio_data = response.content
        content_type = response.headers.get("content-type", "audio/mpeg")

    logger.info(f"[MusicStream] 下载完成: song_id={song_id}, size={len(audio_data)} bytes")

    # 存入缓存
    async with _audio_cache_lock:
        _audio_cache[song_id] = (audio_data, content_type)
        if len(_audio_cache) > _AUDIO_CACHE_MAX:
            evicted_id, _ = _audio_cache.popitem(last=False)
            logger.info(f"[MusicStream] 缓存淘汰: song_id={evicted_id}")

    return audio_data, content_type


@router.get("/music/stream/{song_id}")
async def stream_song(song_id: int, request: Request):
    """代理音乐流，绕过 CDN 的 Referer 限制。

    完整下载 CDN 音频后一次性返回（带 content-length），
    避免流式代理链延迟导致浏览器 waiting/stalled。
    支持 Range 请求（用于拖拽跳转），以及 403/401 时自动刷新 URL 重试。
    内存 LRU 缓存最多 10 首歌，避免重复下载。
    """
    music_service = get_music_service()
    url = await music_service.get_song_play_url(song_id)
    if not url:
        raise HTTPException(status_code=404, detail="Song URL not available")

    try:
        audio_data, content_type = await _get_or_download_audio(song_id, url)
    except httpx.HTTPError as exc:
        logger.warning(f"[MusicStream] Failed to fetch audio for song {song_id}: {exc}")
        raise HTTPException(status_code=502, detail="Failed to fetch audio from CDN")

    # 处理 Range 请求（浏览器拖拽进度条）
    range_header = request.headers.get("range")
    if range_header:
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else len(audio_data) - 1
            end = min(end, len(audio_data) - 1)
            if start > end or start >= len(audio_data):
                raise HTTPException(status_code=416, detail="Range not satisfiable")
            chunk = audio_data[start : end + 1]
            return Response(
                content=chunk,
                status_code=206,
                media_type=content_type,
                headers={
                    "content-range": f"bytes {start}-{end}/{len(audio_data)}",
                    "content-length": str(len(chunk)),
                    "accept-ranges": "bytes",
                    "cache-control": "public, max-age=300",
                },
            )

    # 完整响应
    return Response(
        content=audio_data,
        status_code=200,
        media_type=content_type,
        headers={
            "content-length": str(len(audio_data)),
            "accept-ranges": "bytes",
            "cache-control": "public, max-age=300",
        },
    )


@router.get("/music/playlist/{game_id}")
async def get_playlist(game_id: int):
    """Get the current playlist state for a game."""
    db = SessionLocal()
    try:
        from src.database.models import Game

        game = db.query(Game).filter_by(game_id=game_id).first()
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")

        service = get_music_playlist_service()
        state = service.get_state(db, game_id)
        return state.to_dict()
    finally:
        db.close()


@router.put("/music/playlist/{game_id}")
async def update_playlist(game_id: int, request: PlaylistUpdateRequest):
    """Merge new recommendation songs into the playlist.

    Preserves the currently playing song; only the upcoming queue is replaced.
    """
    db = SessionLocal()
    try:
        service = get_music_playlist_service()
        state = service.merge_songs(
            db=db,
            game_id=game_id,
            songs=[s.model_dump() for s in request.songs],
            mood=request.mood,
            keywords=request.keywords,
        )
        return state.to_dict()
    finally:
        db.close()


@router.post("/music/playlist/{game_id}/sync")
async def sync_playlist_state(game_id: int, request: PlaylistSyncRequest):
    """Sync current playback position and state."""
    db = SessionLocal()
    try:
        service = get_music_playlist_service()
        result = service.sync_state(
            db=db,
            game_id=game_id,
            current_position_ms=request.current_position_ms,
            is_playing=request.is_playing,
            volume=request.volume,
        )
        return result
    finally:
        db.close()


@router.post("/music/playlist/{game_id}/advance")
async def advance_playlist(game_id: int):
    """Advance to the next song in the queue."""
    db = SessionLocal()
    try:
        service = get_music_playlist_service()
        state = service.advance(db, game_id)
        return state.to_dict()
    finally:
        db.close()
