"""Music API router for story-based music recommendation."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
    """
    try:
        music_service = get_music_service()

        # 分析故事并获取推荐
        recommendation = await music_service.analyze_story_for_music(
            story_text=request.story_text,
        )

        # 转换为响应格式
        songs = [
            SongResponse(
                id=song.id,
                name=song.name,
                artists=song.artists,
                album=song.album,
                duration=song.duration,
            )
            for song in recommendation.songs
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
