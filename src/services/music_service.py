"""Music service for story-based music recommendation.

基于故事内容搜索匹配的音乐
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.ai.client import AIClient

logger = logging.getLogger(__name__)


@dataclass
class Song:
    """歌曲信息"""

    id: int
    name: str
    artists: List[str]
    album: str
    duration: int  # 毫秒
    url: Optional[str] = None


@dataclass
class MusicRecommendation:
    """音乐推荐结果"""

    keywords: List[str]
    mood: str
    scene_type: str
    songs: List[Song]
    environment: Optional[str] = None  # 环境氛围
    story_style: Optional[str] = None  # 故事风格
    music_style: Optional[str] = None  # 推荐音乐风格
    instruments: Optional[List[str]] = None  # 适合的乐器
    pacing: Optional[str] = None  # 叙事节奏
    time_weather: Optional[str] = None  # 时间天气
    description: Optional[str] = None  # 音乐氛围描述


class NeteaseMusicClient:
    """网易云音乐 API 客户端"""

    _url_cache: Dict[int, Tuple[str, float]] = {}  # song_id -> (url, expire_timestamp)
    # ★ 降低 TTL 从 20 分钟到 8 分钟
    # 网易云 CDN URL 通常只有 5-10 分钟有效期
    # 20 分钟导致缓存未过期但 URL 已失效（403）
    # 8 分钟在 CDN 典型有效期内，减少 403 概率
    URL_CACHE_TTL = 480  # 8 分钟

    def __init__(self, base_url: Optional[str] = None):
        base_url = base_url or os.getenv("NETEASE_MUSIC_API_URL", "http://localhost:3000")
        # 将 localhost 替换为 127.0.0.1 避免 IPv6 问题
        self.base_url = base_url.replace("localhost", "127.0.0.1")  # type: ignore
        # 禁用连接池，避免 503 错误
        limits = httpx.Limits(max_keepalive_connections=0, max_connections=10)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=30.0, limits=limits, headers=headers)

    async def search(self, keywords: str, limit: int = 10, max_retries: int = 2) -> List[Song]:
        """搜索歌曲

        Args:
            keywords: 搜索关键词
            limit: 返回数量
            max_retries: 最大重试次数（针对 5xx 等暂时性错误）

        Returns:
            歌曲列表
        """
        last_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                url = f"{self.base_url}/search"
                params = {"keywords": keywords, "limit": limit}

                response = await self.client.get(url, params=params)  # type: ignore
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 200:
                    logger.warning(f"Search failed: {data}")
                    return []

                songs = []
                result = data.get("result", {})
                song_list = result.get("songs", [])

                for song_data in song_list:
                    song = Song(
                        id=song_data.get("id", 0),
                        name=song_data.get("name", ""),
                        artists=[a.get("name", "") for a in song_data.get("artists", [])],
                        album=song_data.get("album", {}).get("name", ""),
                        duration=song_data.get("duration", 0),
                    )
                    songs.append(song)

                return songs

            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                if status_code >= 500 and attempt < max_retries:
                    logger.warning(
                        f"[NeteaseMusic] Search got {status_code} for '{keywords}', "
                        f"retrying in 1s... ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(1)
                    continue
                logger.exception(f"Failed to search music: {e}")
                return []
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"[NeteaseMusic] Search error for '{keywords}': {e}, "
                        f"retrying in 1s... ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(1)
                    continue
                logger.exception(f"Failed to search music: {e}")
                return []

        logger.error(f"[NeteaseMusic] Search exhausted retries for '{keywords}': {last_error}")
        return []

    async def get_song_url(self, song_id: int, retry: int = 2) -> Optional[str]:
        """获取歌曲播放 URL

        Args:
            song_id: 歌曲 ID
            retry: 重试次数

        Returns:
            播放 URL
        """
        # 检查缓存
        cached = self._url_cache.get(song_id)
        if cached:
            url, expire_ts = cached
            if time.time() < expire_ts:
                logger.info(f"[MusicCache] 缓存命中: song_id={song_id}")
                return url
            else:
                logger.info(f"[MusicCache] 缓存未命中/过期: song_id={song_id}, 重新获取")
                del self._url_cache[song_id]
        else:
            logger.info(f"[MusicCache] 缓存未命中/过期: song_id={song_id}, 重新获取")

        try:
            url = f"{self.base_url}/song/url"
            params = {"id": song_id}

            logger.info(f"[NeteaseMusic] Getting song URL for id: {song_id}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 200:
                logger.warning(
                    f"[NeteaseMusic] API error: code={data.get('code')}, msg={data.get('message', 'unknown')}"
                )
                return None

            songs = data.get("data", [])
            if songs and len(songs) > 0:
                song_url = songs[0].get("url")
                if song_url:
                    logger.info(f"[NeteaseMusic] Got URL for song {song_id}: {song_url[:50]}...")
                    # 写入缓存
                    self._url_cache[song_id] = (song_url, time.time() + self.URL_CACHE_TTL)
                    return song_url  # type: ignore[no-any-return]
                else:
                    logger.warning(
                        f"[NeteaseMusic] URL is empty for song {song_id}, may be restricted by copyright"
                    )
                    return None

            logger.warning(f"[NeteaseMusic] No data returned for song {song_id}")
            return None

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if retry > 0 and status_code >= 500:
                logger.warning(
                    f"[NeteaseMusic] {status_code} error for song {song_id}, "
                    f"retrying in 1s... ({retry} attempts left)"
                )
                await asyncio.sleep(1)
                return await self.get_song_url(song_id, retry - 1)
            logger.exception(f"[NeteaseMusic] Failed to get song URL: {e}")
            return None
        except Exception as e:
            if retry > 0:
                logger.warning(
                    f"[NeteaseMusic] Error getting URL for song {song_id}: {e}, "
                    f"retrying in 0.5s... ({retry} attempts left)"
                )
                await asyncio.sleep(0.5)
                return await self.get_song_url(song_id, retry - 1)
            logger.exception(f"[NeteaseMusic] Failed to get song URL: {e}")
            return None

    async def close(self):
        await self.client.aclose()


class MusicService:
    """音乐服务：基于故事内容推荐音乐"""

    def __init__(self):
        self.ai_client = AIClient()
        self.music_client = NeteaseMusicClient()

    async def analyze_story_for_music(
        self,
        story_text: str,
        character_settings: Optional[Dict] = None,
    ) -> MusicRecommendation:
        """分析故事内容，提取音乐搜索关键词

        Args:
            story_text: 故事文本
            character_settings: 角色设定

        Returns:
            音乐推荐结果
        """
        # 使用 AI 分析故事情绪和场景
        analysis = await self._analyze_story_mood(story_text, character_settings)

        # 构建搜索关键词
        search_keywords = self._build_search_keywords(analysis)

        # 搜索歌曲 - 使用更多关键词，获取更多结果
        all_songs = []
        # ★ 增加关键词数量和每关键词的搜索数量，提高找到可用歌曲的概率
        for keyword in search_keywords[:8]:  # 增加到8个关键词
            songs = await self.music_client.search(keyword, limit=15)  # 每关键词15首
            all_songs.extend(songs)

        # 去重并限制数量
        seen_ids = set()
        unique_songs: List[Song] = []  # type: ignore[var-annotated]
        for song in all_songs:
            if song.id not in seen_ids and len(unique_songs) < 30:
                seen_ids.add(song.id)
                unique_songs.append(song)

        # ★ 如果歌曲少于15首，使用更通用的关键词补充搜索
        if len(unique_songs) < 15:
            logger.warning(
                f"[MusicService] Only found {len(unique_songs)} songs, searching with generic keywords"
            )
            generic_keywords = ["轻音乐", "纯音乐", "背景音乐", "流行", "经典", "华语"]
            for keyword in generic_keywords:
                if len(unique_songs) >= 15:
                    break
                songs = await self.music_client.search(keyword, limit=15)
                for song in songs:
                    if song.id not in seen_ids and len(unique_songs) < 30:
                        seen_ids.add(song.id)
                        unique_songs.append(song)

        return MusicRecommendation(
            keywords=search_keywords,
            mood=analysis.get("mood", "未知"),
            scene_type=analysis.get("scene_type", "未知"),
            songs=unique_songs,
            environment=analysis.get("environment"),
            story_style=analysis.get("story_style"),
            music_style=analysis.get("music_style"),
            instruments=analysis.get("instruments"),
            pacing=analysis.get("pacing"),
            time_weather=analysis.get("time_weather"),
            description=analysis.get("description"),
        )

    async def _analyze_story_mood(
        self,
        story_text: str,
        character_settings: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """使用 AI 分析故事情绪、场景、背景和风格"""

        # 截取故事前800字用于更全面的分析
        story_preview = story_text[:800] if len(story_text) > 800 else story_text

        # 构建角色设定信息
        setting_info = []
        if character_settings:
            if "era" in character_settings:
                era = character_settings["era"]
                if isinstance(era, dict):
                    setting_info.append(f"时代背景：{era.get('era_description', '')}")
                    setting_info.append(f"时代特征：{era.get('era_name', '')}")
            if "world_description" in character_settings:
                setting_info.append(f"世界观：{character_settings['world_description']}")
            if "character_style" in character_settings:
                setting_info.append(f"角色风格：{character_settings['character_style']}")

        era_info = "\n".join(setting_info) if setting_info else ""

        prompt = f"""请深入分析以下故事片段，为音乐推荐提供精准的关键词。

故事片段：
{story_preview}

{era_info}

请从以下维度分析并返回（JSON格式）：
{{
  "mood": "主要情绪（如：悲伤、欢快、紧张、浪漫、忧郁、激昂、神秘、宁静等）",
  "scene_type": "场景类型（如：战斗、对话、独处、聚会、旅行、探索、回忆等）",
  "environment": "环境氛围（如：古风、现代、未来、自然、都市、荒野、宫廷、江湖等）",
  "story_style": "故事风格（如：武侠、仙侠、科幻、悬疑、治愈、史诗、暗黑等）",
  "music_style": "推荐音乐风格（如：中国风、电子、古典、民谣、摇滚、爵士等）",
  "instruments": ["适合的乐器，如：古筝、笛子、钢琴、小提琴、电子合成器等"],
  "pacing": "叙事节奏（如：舒缓、紧凑、急促、悠然、跌宕起伏等）",
  "time_weather": "时间天气（如：清晨、黄昏、夜晚、雨天、雪天、雾天、晴朗等）",
  "keywords": ["5-8个中文音乐搜索关键词，结合情绪、场景、时代、风格、节奏"],
  "description": "简短的音乐氛围描述（30字以内，包含时代和风格特征）"
}}

分析要求：
1. 考虑故事的时代背景（古代/现代/未来）
2. 考虑故事的风格类型（武侠/仙侠/科幻等）
3. 考虑场景环境（室内/室外/自然/都市等）
4. 分析叙事节奏：故事是舒缓展开还是紧凑推进？
5. 识别时间天气：故事发生在什么时段？天气如何？
6. 选择符合时代、风格和节奏的乐器
7. 关键词要具体，便于搜索到匹配的音乐

只返回JSON，不要有其他内容。"""

        try:
            response = self.ai_client.call(
                system_prompt="你是一位精通音乐与文学的专家，擅长根据故事的背景、时代、风格和情绪，推荐最契合的音乐。你熟悉各种音乐类型：中国传统民乐、古典音乐、现代流行、电子音乐、影视配乐等。",
                user_prompt=prompt,
                temperature=0.7,
            )

            # 解析 JSON 响应
            import json

            # 尝试提取 JSON
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            return result  # type: ignore[no-any-return]

        except Exception as e:
            logger.warning(f"Failed to analyze story mood: {e}")
            # 返回默认分析
            return {
                "mood": "平静",
                "scene_type": "叙事",
                "keywords": ["轻音乐", "背景音乐", "纯音乐"],
                "description": "舒缓的背景音乐",
            }

    # 情绪到音乐风格的映射
    MOOD_TO_MUSIC_STYLE = {
        # 悲伤类
        "悲伤": ["伤感", "抒情", "慢歌"],
        "忧郁": ["伤感", "抒情", "蓝调"],
        "沉思": ["轻音乐", "钢琴", "冥想"],
        "孤独": ["伤感", "民谣", "独白"],
        # 紧张类
        "紧张": ["史诗", "战斗", "激昂"],
        "悬疑": ["悬疑", "惊悚", "氛围"],
        "恐惧": ["恐怖", "氛围", "暗黑"],
        # 积极类
        "欢快": ["轻快", "流行", "开心"],
        "喜悦": ["欢快", "庆祝", "流行"],
        "激昂": ["史诗", "摇滚", "战斗"],
        "浪漫": ["浪漫", "情歌", "甜蜜"],
        "温馨": ["温暖", "治愈", "轻音乐"],
        # 平静类
        "平静": ["轻音乐", "纯音乐", "背景音乐"],
        "放松": ["轻音乐", "冥想", "自然"],
        "专注": ["轻音乐", "学习", "阅读"],
    }

    def _build_search_keywords(self, analysis: Dict[str, Any]) -> List[str]:
        """构建搜索关键词列表 - 综合考虑情绪、场景、时代、风格"""
        keywords = []

        # 获取各维度分析结果
        mood = analysis.get("mood", "")
        analysis.get("scene_type", "")  # scene not used directly
        environment = analysis.get("environment", "")
        story_style = analysis.get("story_style", "")
        music_style = analysis.get("music_style", "")
        instruments = analysis.get("instruments", [])
        ai_keywords = analysis.get("keywords", [])

        # 1. 优先使用 AI 推荐的完整关键词（已经综合考虑了多维度）
        abstract_words = ["沉思", "悬疑", "独处", "阅读", "思考", "氛围", "感觉"]
        for kw in ai_keywords:
            if kw and kw not in keywords and kw not in abstract_words:
                keywords.append(kw)

        # 2. 添加音乐风格关键词
        if music_style and music_style not in keywords:
            keywords.append(music_style)

        # 3. 添加环境/时代关键词
        environment_keywords = {
            "古风": ["古风", "中国风", "传统"],
            "现代": ["流行", "现代"],
            "未来": ["电子", "科幻", "未来"],
            "自然": ["自然", "清新", "田园"],
            "都市": ["都市", "流行", "现代"],
            "荒野": ["荒野", "苍凉", "自然"],
            "宫廷": ["宫廷", "古典", "庄重"],
            "江湖": ["武侠", "江湖", "古风"],
        }
        if environment:
            for env_key, env_styles in environment_keywords.items():
                if env_key in environment:
                    for style in env_styles:
                        if style not in keywords:
                            keywords.append(style)
                    break

        # 4. 添加故事风格关键词
        style_keywords = {
            "武侠": ["武侠", "江湖", "古风"],
            "仙侠": ["仙侠", "玄幻", "古风"],
            "科幻": ["科幻", "电子", "未来"],
            "悬疑": ["悬疑", "紧张", "氛围"],
            "治愈": ["治愈", "温暖", "轻音乐"],
            "史诗": ["史诗", "宏大", "交响"],
            "暗黑": ["暗黑", "哥特", "氛围"],
        }
        if story_style:
            for style_key, style_list in style_keywords.items():
                if style_key in story_style:
                    for style in style_list:
                        if style not in keywords:
                            keywords.append(style)
                    break

        # 5. 添加乐器关键词（有助于找到特定风格的音乐）
        for instrument in instruments[:2]:  # 最多取2个乐器
            if instrument and instrument not in keywords:
                keywords.append(instrument)

        # 6. 情绪映射作为补充
        if mood:
            for mood_key, styles in self.MOOD_TO_MUSIC_STYLE.items():
                if mood_key in mood:
                    for style in styles:
                        if style not in keywords:
                            keywords.append(style)
                    break

        # 保底关键词
        if not keywords:
            keywords = ["轻音乐", "背景音乐", "纯音乐"]

        # 构建最终搜索关键词（组合关键词提高匹配度）
        extended_keywords = []

        # 优先使用原始关键词
        for kw in keywords[:4]:
            extended_keywords.append(kw)

        # 组合关键词（风格 + 情绪）
        if music_style and mood:
            combo = f"{music_style} {mood}"
            if combo not in extended_keywords:
                extended_keywords.append(combo)

        # 添加通用后缀
        final_keywords = []
        for kw in extended_keywords[:5]:
            final_keywords.append(kw)
            if "音乐" not in kw and "歌曲" not in kw and len(final_keywords) < 6:
                final_keywords.append(f"{kw} 音乐")

        return final_keywords[:6]  # 最多返回6个关键词

    async def get_song_play_url(self, song_id: int) -> Optional[str]:
        """获取歌曲播放 URL"""
        return await self.music_client.get_song_url(song_id)  # type: ignore[no-any-return]

    async def close(self):
        await self.music_client.close()


# 全局服务实例
_music_service: Optional[MusicService] = None


def get_music_service() -> MusicService:
    """获取音乐服务实例"""
    global _music_service
    if _music_service is None:
        _music_service = MusicService()
    return _music_service
