"""Music service for story-based music recommendation.

基于故事内容搜索匹配的音乐
"""

import logging
import os
import time
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional, Protocol, Sequence, TypeVar

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
    source: str = "netease"


@dataclass
class CachedSong:
    """Verified song with a playable URL cached for recommendation reuse."""

    id: int
    name: str
    artists: List[str]
    album: str
    duration: int
    url: str
    url_expires_at: float
    verified_at: float
    source: str = "netease"


@dataclass
class CachedMusicPool:
    """Cached analyzed story intent and verified playable songs."""

    analysis: Dict[str, Any]
    verified_songs: List[CachedSong]
    created_at: float


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
    music_brief: Optional["MusicBrief"] = None


@dataclass(frozen=True)
class MusicBrief:
    """Structured story-to-music intent shared by search and generation."""

    mood: str
    scene_type: str
    era_or_environment: str
    pacing: str
    energy: str
    instruments: List[str]
    search_queries: List[str]
    negative_cues: List[str] = field(default_factory=list)
    generation_prompt: str = ""

    @classmethod
    def default(cls) -> "MusicBrief":
        return cls(
            mood="平静",
            scene_type="叙事",
            era_or_environment="通用",
            pacing="舒缓",
            energy="中低",
            instruments=["钢琴", "弦乐"],
            search_queries=["轻音乐", "背景音乐", "纯音乐"],
            negative_cues=["人声", "歌词", "强节拍流行"],
            generation_prompt=(
                "Create a seamless instrumental ambience loop for narrative gameplay, "
                "45-90 seconds, no vocals, no lyrics, gentle background presence."
            ),
        )

    @classmethod
    def from_analysis(cls, analysis: Dict[str, Any]) -> "MusicBrief":
        if not isinstance(analysis, dict):
            return cls.default()

        instruments = analysis.get("instruments")
        if not isinstance(instruments, list):
            instruments = cls.default().instruments
        normalized_instruments = [str(item) for item in instruments if item]

        search_queries = analysis.get("search_queries") or analysis.get("keywords")
        if not isinstance(search_queries, list):
            search_queries = cls.default().search_queries
        normalized_queries = [str(item) for item in search_queries if item]

        negative_cues = analysis.get("negative_cues")
        if not isinstance(negative_cues, list):
            negative_cues = cls.default().negative_cues
        normalized_negative = [str(item) for item in negative_cues if item]

        mood = str(analysis.get("mood") or cls.default().mood)
        scene_type = str(analysis.get("scene_type") or cls.default().scene_type)
        era_or_environment = str(
            analysis.get("era_or_environment")
            or analysis.get("environment")
            or cls.default().era_or_environment
        )
        pacing = str(analysis.get("pacing") or cls.default().pacing)
        energy = str(analysis.get("energy") or cls.default().energy)
        prompt = str(analysis.get("generation_prompt") or "").strip()
        if not prompt:
            prompt = (
                "Create a seamless instrumental ambience loop for narrative gameplay. "
                f"Mood: {mood}. Scene: {scene_type}. Setting: {era_or_environment}. "
                f"Pacing: {pacing}. Energy: {energy}. "
                f"Instruments: {', '.join(normalized_instruments)}. "
                "No vocals, no lyrics."
            )

        return cls(
            mood=mood,
            scene_type=scene_type,
            era_or_environment=era_or_environment,
            pacing=pacing,
            energy=energy,
            instruments=normalized_instruments or cls.default().instruments,
            search_queries=normalized_queries or cls.default().search_queries,
            negative_cues=normalized_negative,
            generation_prompt=prompt,
        )

    def to_analysis(self) -> Dict[str, Any]:
        return {
            "mood": self.mood,
            "scene_type": self.scene_type,
            "environment": self.era_or_environment,
            "era_or_environment": self.era_or_environment,
            "pacing": self.pacing,
            "energy": self.energy,
            "instruments": self.instruments,
            "keywords": self.search_queries,
            "search_queries": self.search_queries,
            "negative_cues": self.negative_cues,
            "generation_prompt": self.generation_prompt,
        }


@dataclass(frozen=True)
class MusicProviderPolicy:
    """Provider decision for immediate search and optional premium generation."""

    use_netease: bool
    enqueue_ai_generation: bool

    @classmethod
    def select(cls, is_member: bool, ai_music_enabled: bool) -> "MusicProviderPolicy":
        return cls(
            use_netease=True,
            enqueue_ai_generation=bool(is_member and ai_music_enabled),
        )


@dataclass
class MusicGenerationResult:
    songs: List[Song]
    generation_error: Optional[str]
    used_fallback: bool


class MusicContextBuilder:
    """Build search and generation intent from story analysis."""

    def build_brief(self, analysis: Dict[str, Any]) -> MusicBrief:
        return MusicBrief.from_analysis(analysis)

    def build_search_queries(self, brief: MusicBrief) -> List[str]:
        queries: List[str] = []
        blocked = set(brief.negative_cues)
        candidates = [
            *brief.search_queries,
            f"{brief.mood} {brief.scene_type}",
            f"{brief.era_or_environment} {brief.scene_type}",
            *[
                f"{brief.era_or_environment} {instrument}"
                for instrument in brief.instruments[:2]
            ],
            f"{brief.mood} {brief.pacing}",
            f"{brief.energy} {' '.join(brief.instruments[:2])}",
            f"{brief.scene_type} {' '.join(brief.instruments[:2])}",
        ]
        for query in candidates:
            normalized = query.strip()
            if not normalized or normalized in queries:
                continue
            if any(cue and cue in normalized for cue in blocked):
                continue
            queries.append(normalized)
        return queries or MusicBrief.default().search_queries


class MusicTrack(Protocol):
    id: int
    name: str
    artists: List[str]
    album: str


TMusicTrack = TypeVar("TMusicTrack", bound=MusicTrack)


class MusicResultRanker:
    """Rank Netease results against a structured music brief."""

    def rank(self, songs: Sequence[TMusicTrack], brief: MusicBrief) -> List[TMusicTrack]:
        positive_terms = [
            brief.mood,
            brief.scene_type,
            brief.era_or_environment,
            brief.pacing,
            *brief.instruments,
            *brief.search_queries,
        ]
        positive_terms = [
            term.strip() for term in positive_terms if len(term.strip()) >= 2
        ]

        def score(song: MusicTrack) -> int:
            haystack = " ".join([song.name, song.album, *song.artists])
            value = 0
            for term in positive_terms:
                if term and term in haystack:
                    value += 10
            for cue in brief.negative_cues:
                if cue and cue in haystack:
                    value -= 100
            return value

        scored = [(score(song), index, song) for index, song in enumerate(songs)]
        if not any(value > 0 for value, _, _ in scored):
            return list(songs)
        return [song for _, _, song in sorted(scored, key=lambda item: item[0], reverse=True)]


@dataclass(frozen=True)
class MusicGenerationJob:
    """Background AI music generation job descriptor."""

    game_id: int
    brief: MusicBrief
    provider: str
    model: str
    status: str
    source: str
    prompt_text: str
    brief_hash: str

    @classmethod
    def create(
        cls,
        game_id: int,
        brief: MusicBrief,
        provider: str,
        model: str,
    ) -> "MusicGenerationJob":
        brief_hash = sha256(str(brief.to_analysis()).encode("utf-8")).hexdigest()
        return cls(
            game_id=game_id,
            brief=brief,
            provider=provider,
            model=model,
            status="pending",
            source="ai_generated",
            prompt_text=brief.generation_prompt,
            brief_hash=brief_hash,
        )


class MusicGenerationCoordinator:
    """Coordinates generated-track fallback without owning a provider."""

    def handle_generation_result(
        self,
        generated_track: Optional[Song],
        netease_songs: List[Song],
        error_message: Optional[str] = None,
    ) -> MusicGenerationResult:
        if generated_track is not None:
            return MusicGenerationResult(
                songs=[generated_track],
                generation_error=None,
                used_fallback=False,
            )
        return MusicGenerationResult(
            songs=netease_songs,
            generation_error=error_message,
            used_fallback=True,
        )


class NeteaseMusicClient:
    """网易云音乐 API 客户端"""

    def __init__(self, base_url: Optional[str] = None) -> None:
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

    async def search(self, keywords: str, limit: int = 10) -> List[Song]:
        """搜索歌曲

        Args:
            keywords: 搜索关键词
            limit: 返回数量

        Returns:
            歌曲列表
        """
        try:
            url = f"{self.base_url}/search"
            params: Dict[str, str | int] = {"keywords": keywords, "limit": limit}

            response = await self.client.get(url, params=params)
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

        except Exception as e:
            logger.exception(f"Failed to search music: {e}")
            return []

    async def get_song_url(self, song_id: int, retry: int = 2) -> Optional[str]:
        """获取歌曲播放 URL

        Args:
            song_id: 歌曲 ID
            retry: 重试次数

        Returns:
            播放 URL
        """
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
                    return song_url  # type: ignore[no-any-return]
                else:
                    logger.warning(
                        f"[NeteaseMusic] URL is empty for song {song_id}, may be restricted by copyright"
                    )
                    return None

            logger.warning(f"[NeteaseMusic] No data returned for song {song_id}")
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                logger.warning(
                    "[NeteaseMusic] Upstream unavailable for song %s; skipping URL",
                    song_id,
                )
                return None
            logger.exception(f"[NeteaseMusic] Failed to get song URL: {e}")
            return None
        except Exception as e:
            logger.exception(f"[NeteaseMusic] Failed to get song URL: {e}")
            return None

    async def close(self) -> None:
        await self.client.aclose()


class MusicService:
    """音乐服务：基于故事内容推荐音乐"""

    POOL_CACHE_TTL = 3600
    ANALYSIS_CACHE_TTL = 3600
    SONG_URL_TTL = 600

    _analysis_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
    _pool_cache: Dict[str, tuple[CachedMusicPool, float]] = {}

    def __init__(self) -> None:
        self.ai_client = AIClient()
        self.music_client = NeteaseMusicClient()
        self.context_builder = MusicContextBuilder()
        self.result_ranker = MusicResultRanker()

    async def analyze_story_for_music(
        self,
        story_text: str,
        character_settings: Optional[Dict[str, Any]] = None,
        refresh: bool = False,
    ) -> MusicRecommendation:
        """分析故事内容，提取音乐搜索关键词

        Args:
            story_text: 故事文本
            character_settings: 角色设定
            refresh: 刷新推荐时保留接口兼容；当前实现重新分析并重新搜索

        Returns:
            音乐推荐结果
        """
        pool = await self._get_or_build_pool(story_text, character_settings, refresh)
        analysis = pool.analysis
        music_brief = self.context_builder.build_brief(analysis)
        selected_songs = self._random_select_songs(pool)
        search_keywords = self.context_builder.build_search_queries(music_brief)

        return MusicRecommendation(
            keywords=search_keywords,
            mood=analysis.get("mood", "未知"),
            scene_type=analysis.get("scene_type", "未知"),
            songs=[
                Song(
                    id=song.id,
                    name=song.name,
                    artists=song.artists,
                    album=song.album,
                    duration=song.duration,
                    url=song.url,
                    source=song.source,
                )
                for song in selected_songs
            ],
            environment=analysis.get("environment"),
            story_style=analysis.get("story_style"),
            music_style=analysis.get("music_style"),
            instruments=analysis.get("instruments"),
            pacing=analysis.get("pacing"),
            time_weather=analysis.get("time_weather"),
            description=analysis.get("description"),
            music_brief=music_brief,
        )

    def _story_hash(self, story_text: str) -> str:
        """Return a stable cache key for story text."""
        return sha256(story_text.encode("utf-8")).hexdigest()

    def _random_select_songs(self, pool: CachedMusicPool) -> List[CachedSong]:
        """Return a small unique ranked playlist from the verified pool."""
        seen_ids: set[int] = set()
        songs: List[CachedSong] = []
        for song in pool.verified_songs:
            if not song.url or song.id in seen_ids:
                continue
            songs.append(song)
            seen_ids.add(song.id)
        if len(songs) <= 5:
            return songs
        brief = self.context_builder.build_brief(pool.analysis)
        ranked = self.result_ranker.rank(songs, brief)
        return ranked[: min(8, len(ranked))]

    async def _get_or_build_pool(
        self,
        story_text: str,
        character_settings: Optional[Dict[str, Any]] = None,
        refresh: bool = False,
    ) -> CachedMusicPool:
        story_hash = self._story_hash(story_text)
        now = time.time()

        cached_pool = self._pool_cache.get(story_hash)
        if not refresh and cached_pool and now - cached_pool[1] < self.POOL_CACHE_TTL:
            pool = cached_pool[0]
            await self._refresh_pool_urls(pool, supplement=False)
            return pool

        cached_analysis = self._analysis_cache.get(story_hash)
        if cached_analysis and now - cached_analysis[1] < self.ANALYSIS_CACHE_TTL:
            analysis = cached_analysis[0]
        else:
            analysis = await self._analyze_story_mood(story_text, character_settings)
            self._analysis_cache[story_hash] = (analysis, now)

        pool = CachedMusicPool(
            analysis=analysis,
            verified_songs=[],
            created_at=now,
        )
        await self._supplement_pool(pool)
        self._pool_cache[story_hash] = (pool, now)
        return pool

    async def _refresh_pool_urls(self, pool: CachedMusicPool, supplement: bool = True) -> None:
        now = time.time()
        refreshed_songs: List[CachedSong] = []
        for song in pool.verified_songs:
            if song.url and song.url_expires_at > now:
                refreshed_songs.append(song)
                continue

            fresh_url = await self.music_client.get_song_url(song.id)
            if fresh_url:
                song.url = fresh_url
                song.url_expires_at = time.time() + self.SONG_URL_TTL
                song.verified_at = time.time()
                refreshed_songs.append(song)

        pool.verified_songs = refreshed_songs
        if supplement and len(pool.verified_songs) < 5:
            await self._supplement_pool(pool)

    async def _supplement_pool(self, pool: CachedMusicPool) -> None:
        seen_ids = {song.id for song in pool.verified_songs}
        brief = self.context_builder.build_brief(pool.analysis)
        search_keywords = self.context_builder.build_search_queries(brief)
        if len(pool.verified_songs) < 5:
            search_keywords.extend(["轻音乐", "纯音乐", "背景音乐"])

        for keyword in search_keywords[:8]:
            if len(pool.verified_songs) >= 20:
                break
            songs = await self.music_client.search(keyword, limit=10)
            for song in songs:
                if song.id in seen_ids or len(pool.verified_songs) >= 20:
                    continue
                song_url = song.url or await self.music_client.get_song_url(song.id)
                if not song_url:
                    continue
                now = time.time()
                pool.verified_songs.append(
                    CachedSong(
                        id=song.id,
                        name=song.name,
                        artists=song.artists,
                        album=song.album,
                        duration=song.duration,
                        url=song_url,
                        url_expires_at=now + self.SONG_URL_TTL,
                        verified_at=now,
                        source=song.source,
                    )
                )
                seen_ids.add(song.id)

    async def _analyze_story_mood(
        self,
        story_text: str,
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """使用 AI 分析故事情绪、场景、背景和风格"""

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

        prompt = f"""请深入分析以下故事全文，为音乐推荐提供精准的关键词。

故事全文：
{story_text}

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
  "energy": "音乐能量（如：低、中低、中、高、爆发等）",
  "time_weather": "时间天气（如：清晨、黄昏、夜晚、雨天、雪天、雾天、晴朗等）",
  "keywords": ["5-8个中文音乐搜索关键词，结合情绪、场景、时代、风格、节奏"],
  "search_queries": ["5-8个网易云搜索词，组合情绪、时代、场景、能量、乐器"],
  "negative_cues": ["不适合当前场景的音乐特征，如：人声、甜蜜流行、强烈舞曲等"],
  "generation_prompt": "英文生成提示词：instrumental ambience loop, no vocals, no lyrics",
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
8. generation_prompt 默认必须是纯音乐/氛围 loop，不要人声或歌词

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
            if not isinstance(result, dict):
                raise ValueError("Music analysis response is not a JSON object")
            return result

        except Exception as e:
            logger.warning(f"Failed to analyze story mood: {e}")
            # 返回默认分析
            return {
                "mood": "平静",
                "scene_type": "叙事",
                "environment": "通用",
                "pacing": "舒缓",
                "energy": "中低",
                "instruments": ["钢琴", "弦乐"],
                "keywords": ["轻音乐", "背景音乐", "纯音乐"],
                "search_queries": ["轻音乐", "背景音乐", "纯音乐"],
                "negative_cues": ["人声", "歌词", "强节拍流行"],
                "generation_prompt": MusicBrief.default().generation_prompt,
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

    def _build_search_keywords(
        self,
        analysis: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """构建搜索关键词列表 - 综合考虑情绪、场景、时代、风格"""
        if character_settings:
            era = character_settings.get("era")
            if isinstance(era, dict):
                era_name = str(era.get("era_name") or "")
                environment_text = str(analysis.get("environment") or "")
                if era_name and era_name not in {"现代", "当代"} and "古" not in environment_text:
                    analysis = dict(analysis)
                    analysis["environment"] = f"古风 {environment_text}".strip()

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
        return await self.music_client.get_song_url(song_id)

    async def close(self) -> None:
        await self.music_client.close()


# 全局服务实例
_music_service: Optional[MusicService] = None


def get_music_service() -> MusicService:
    """获取音乐服务实例"""
    global _music_service
    if _music_service is None:
        _music_service = MusicService()
    return _music_service
