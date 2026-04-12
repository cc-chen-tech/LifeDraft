"""Music API router for story-based music recommendation."""

import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.deps import get_current_user_optional
from src.services.music_service import get_music_service

logger = logging.getLogger(__name__)

router = APIRouter()


class MusicRecommendationRequest(BaseModel):
    """音乐推荐请求"""

    story_text: str
    game_id: Optional[int] = None


class SongResponse(BaseModel):
    """歌曲响应"""

    id: int
    name: str
    artists: List[str]
    album: str
    duration: int
    url: Optional[str] = None


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
    songs: List[SongResponse]


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

        logger.info(f"[MusicAPI] Fetched {len(url_map)}/{len(recommendation.songs)} song URLs")

        # 过滤掉没有有效 URL 的歌曲
        filtered_out = [song for song in recommendation.songs if song.id not in url_map]
        if filtered_out:
            filtered_ids = [s.id for s in filtered_out]
            logger.info(
                f"[MusicAPI] Filtered out {len(filtered_out)} songs without URL: {filtered_ids}"
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
            songs=songs,
        )

    except Exception as e:
        logger.exception(f"Failed to recommend music: {e}")
        raise HTTPException(status_code=500, detail=f"音乐推荐失败: {str(e)}")


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
                )
                for song in songs
            ]
        }

    except Exception as e:
        logger.exception(f"Failed to search music: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/music/stream/{song_id}")
async def stream_song(song_id: int, request: Request):
    """代理音乐流，绕过 CDN 的 Referer 限制。

    浏览器直接请求网易云 CDN 会被 403/ORB 拦截（因为 Referer 是 localhost），
    通过后端代理请求并流式返回音频数据即可绕过。
    支持 Range 请求转发（用于拖拽跳转），以及 403/401 时自动刷新 URL 重试。
    """
    music_service = get_music_service()
    url = await music_service.get_song_play_url(song_id)
    if not url:
        raise HTTPException(status_code=404, detail="Song URL not available")

    async def _do_stream(target_url: str) -> StreamingResponse:
        """向 CDN 发起流式请求并返回 StreamingResponse。"""
        client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        try:
            # 不发送 Referer，避免 CDN 拒绝；转发 Range 头以支持拖拽跳转
            cdn_headers: dict[str, str] = {"Referer": ""}
            if "range" in request.headers:
                cdn_headers["Range"] = request.headers["range"]

            response = await client.send(
                client.build_request("GET", target_url, headers=cdn_headers),
                stream=True,
            )
            return response, client
        except httpx.HTTPError as exc:
            await client.aclose()
            raise exc

    try:
        response, client = await _do_stream(url)

        # 如果 CDN 返回 403/401（URL 过期），尝试刷新 URL 重试一次
        if response.status_code in (403, 401):
            logger.info(
                f"[MusicStream] CDN returned {response.status_code} for song {song_id}, refreshing URL..."
            )
            await response.aclose()
            await client.aclose()

            fresh_url = await music_service.get_song_play_url(song_id)
            if not fresh_url:
                raise HTTPException(status_code=404, detail="Song URL not available after refresh")

            response, client = await _do_stream(fresh_url)

        if response.status_code not in (200, 206):
            status = response.status_code
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=status, detail="CDN request failed")

        async def audio_generator():
            try:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    yield chunk
            except Exception:
                # 客户端断开连接是正常行为（切歌），静默处理
                pass
            finally:
                try:
                    await response.aclose()
                except Exception:
                    pass
                try:
                    await client.aclose()
                except Exception:
                    pass

        content_type = response.headers.get("content-type", "audio/mpeg")
        resp_headers: dict[str, str] = {
            "accept-ranges": "bytes",
            "cache-control": "public, max-age=300",
        }
        # 转发 content-range 头（206 Partial Content 时需要）
        if "content-range" in response.headers:
            resp_headers["content-range"] = response.headers["content-range"]
        # 注意：不设置 content-length。流式响应中设置该头会导致客户端提前断开时
        # h11 报 "Too little data for declared Content-Length" 错误。

        return StreamingResponse(
            audio_generator(),
            status_code=response.status_code,
            media_type=content_type,
            headers=resp_headers,
        )
    except httpx.HTTPError as exc:
        logger.warning(f"[MusicStream] Failed to fetch audio for song {song_id}: {exc}")
        raise HTTPException(status_code=502, detail="Failed to fetch audio from CDN")
