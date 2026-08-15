"""Pydantic request/response models for all API endpoints."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, Field

from src.api.input_limits import (
    CUSTOM_ACTION_MAX_CHARS,
    FEEDBACK_MAX_CHARS,
    FULL_STORY_MAX_CHARS,
    LIFE_VISION_MAX_CHARS,
    NAME_MAX_CHARS,
    REPLACEMENT_SEGMENT_MAX_CHARS,
    STORY_DIALOGUE_MAX_CHARS,
    STORY_REWRITE_INSTRUCTION_MAX_CHARS,
    VOICE_TEXT_MAX_CHARS,
    CharacterSettingsPayload,
)

# ==================== Auth ====================


class RegisterRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=NAME_MAX_CHARS)


class LoginRequest(BaseModel):
    private_id: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("private_id", "private_key"),
    )


class PhoneLoginRequest(BaseModel):
    phone_number: str = Field(..., min_length=1)
    verification_code: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: "UserInfo"


class UserInfo(BaseModel):
    user_id: int
    public_id: str
    display_name: Optional[str] = None
    private_id: Optional[str] = None  # Only returned on register


# ==================== Games ====================


class CreateGameRequest(BaseModel):
    character_settings: CharacterSettingsPayload
    player_name: str = Field(..., max_length=NAME_MAX_CHARS)
    life_vision: str = Field(..., max_length=LIFE_VISION_MAX_CHARS)
    language: str = "zh"
    constraint_level: str = "expert"


class GameListItem(BaseModel):
    game_id: int
    player_name: str
    week: int
    age: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    has_progress: bool = False


class GameStateResponse(BaseModel):
    game_id: int
    player_state: Dict[str, Any]
    progress: Dict[str, Any]
    round_info: Dict[str, Any]
    current_event: Optional[Dict[str, Any]] = None
    timeline: Optional[Dict[str, Any]] = None
    constraint_level: str = "expert"
    narrative_style_id: Optional[str] = None
    narrative_style_name: Optional[str] = None


# ==================== Achievements & Life Review ====================


class AchievementItem(BaseModel):
    id: str
    name: str
    description: str
    rarity: str  # common, rare, epic, legendary
    dimension: str
    unlocked_at_week: int = 0
    icon: str = ""


class AchievementList(BaseModel):
    list: List[AchievementItem]
    count: int


class TurningPointItem(BaseModel):
    week: int
    description: str
    impact_score: float


class ResourceCurves(BaseModel):
    energy: List[int]
    mood: List[int]
    knowledge: List[int]


class RelationshipNode(BaseModel):
    name: str
    affinity: int


class RelationshipEdge(BaseModel):
    source: str
    target: str
    strength: float


class RelationshipNetwork(BaseModel):
    nodes: List[RelationshipNode]
    edges: List[RelationshipEdge]


class BadgeWallItem(BaseModel):
    id: str
    name: str
    rarity: str
    unlocked_at_week: int


class LifeReviewData(BaseModel):
    personality_labels: List[str]
    key_turning_points: List[TurningPointItem]
    resource_curves: ResourceCurves
    achievement_badge_wall: List[BadgeWallItem]
    relationship_network: RelationshipNetwork
    life_motto: str
    play_duration_minutes: int
    total_decisions: int
    favorite_choice_type: str


class SaveGameResponse(BaseModel):
    success: bool
    message: str = ""


# ==================== Character Creation ====================


class GenerateSettingRequest(BaseModel):
    setting_type: Literal["era", "age", "gender", "world", "family", "relationships", "traits"] = Field(
        ..., description="era|age|gender|world|family|relationships|traits"
    )
    player_name: str = Field(..., max_length=NAME_MAX_CHARS)
    life_vision: str = Field(..., max_length=LIFE_VISION_MAX_CHARS)
    previous_settings: CharacterSettingsPayload = Field(default_factory=dict)
    feedback: Optional[str] = Field(None, max_length=FEEDBACK_MAX_CHARS)
    language: str = "zh"


class GenerateStoryOriginRequest(BaseModel):
    player_name: str = Field(..., max_length=NAME_MAX_CHARS)
    life_vision: str = Field(..., max_length=LIFE_VISION_MAX_CHARS)
    previous_settings: CharacterSettingsPayload = Field(default_factory=dict)
    feedback: Optional[str] = Field(None, max_length=FEEDBACK_MAX_CHARS)
    language: str = "zh"


class GenerateRelationshipRequest(BaseModel):
    player_name: str = Field(..., max_length=NAME_MAX_CHARS)
    life_vision: str = Field(..., max_length=LIFE_VISION_MAX_CHARS)
    previous_settings: CharacterSettingsPayload = Field(default_factory=dict)
    existing_people: List[Dict[str, Any]] = Field(default_factory=list)
    person_index: int = 0
    total_needed: int = 3
    feedback: Optional[str] = Field(None, max_length=FEEDBACK_MAX_CHARS)
    language: str = "zh"


class GenerateAttributesRequest(BaseModel):
    character_settings: CharacterSettingsPayload
    language: str = "zh"


class UpdateGameSettingsRequest(BaseModel):
    constraint_level: Optional[str] = None


class UpdateCharacterSettingsRequest(BaseModel):
    character_settings: CharacterSettingsPayload = Field(..., min_length=1)
    player_name: Optional[str] = Field(None, max_length=NAME_MAX_CHARS)
    life_vision: Optional[str] = Field(None, max_length=LIFE_VISION_MAX_CHARS)


class StoryOriginPayload(BaseModel):
    revision: int = Field(..., ge=1)
    start_date: str
    starting_age: int = Field(..., ge=0, le=120)
    era_description: str = Field(..., min_length=1)
    life_stage_description: str = Field(..., min_length=1)
    world_context: str = Field(..., min_length=1)


class ReplaceStoryOriginRequest(BaseModel):
    expected_revision: int = Field(..., ge=1)
    story_origin: StoryOriginPayload


class ReplaceStoryOriginResponse(BaseModel):
    success: bool = True
    story_origin: Dict[str, Any]
    timeline: Dict[str, Any]
    character_settings: Dict[str, Any]


class UpdateNarrativeStyleRequest(BaseModel):
    style_id: str


class OpeningStoryRequest(BaseModel):
    character_settings: CharacterSettingsPayload
    player_name: str = Field(..., max_length=NAME_MAX_CHARS)
    life_vision: str = Field(..., max_length=LIFE_VISION_MAX_CHARS)
    language: str = "zh"


class RelationshipsSummaryRequest(BaseModel):
    player_name: str = Field(..., max_length=NAME_MAX_CHARS)
    life_vision: str = Field(..., max_length=LIFE_VISION_MAX_CHARS)
    previous_settings: CharacterSettingsPayload = Field(default_factory=dict)
    key_people: List[Dict[str, Any]] = Field(default_factory=list)
    language: str = "zh"


# ==================== Presets ====================


class CreatePresetRequest(BaseModel):
    preset_name: str = Field(..., min_length=1, max_length=NAME_MAX_CHARS)
    player_name: str = Field(..., max_length=NAME_MAX_CHARS)
    life_vision: str = Field("", max_length=LIFE_VISION_MAX_CHARS)
    character_settings: CharacterSettingsPayload = Field(default_factory=dict)


class PresetInfo(BaseModel):
    preset_id: int
    preset_name: str
    player_name: str
    life_vision: Optional[str] = None
    character_settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


# ==================== Gameplay ====================


class MakeChoiceRequest(BaseModel):
    option_index: int = Field(..., ge=0)
    event_id: Optional[str] = None
    revision: Optional[int] = Field(default=None, ge=1)


class CustomChoiceRequest(BaseModel):
    custom_text: str = Field(..., min_length=1, max_length=CUSTOM_ACTION_MAX_CHARS)


class GenerateSummaryRequest(BaseModel):
    weeks: int = Field(default=10, ge=1)


class ChoiceResultResponse(BaseModel):
    story_continuation: str = ""
    summary: str = ""
    effects_applied: Dict[str, Any] = Field(default_factory=dict)
    effects_requested: Dict[str, Any] = Field(default_factory=dict)
    resource_warnings: List[Dict[str, Any]] = Field(default_factory=list)
    need_weekly_summary: bool = False
    weekly_summary: Optional[str] = None
    bonus_effects: Optional[Dict[str, Any]] = None
    game_over: bool = False
    next_timeline: Optional[Dict[str, Any]] = None


class VoiceReadingSettingsResponse(BaseModel):
    member_required: bool = True
    enabled: bool = False
    available_voice_colors: List[str] = Field(default_factory=list)
    selected_voice_color: Optional[str] = None
    uploaded_voice_available: bool = False
    auto_read_enabled: bool = True
    selected_speed: float = 1.0
    tts_provider: str = "minimax"
    tts_model: str = "speech-02-turbo"
    tts_provider_available: bool = False
    backend_audio_enabled: bool = False
    playback_mode: str = "unavailable"


class VoiceReadingSettingsUpdateRequest(BaseModel):
    selected_voice_color: Optional[str] = None
    auto_read_enabled: Optional[bool] = None
    selected_speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)


class VoiceUploadConsentRequest(BaseModel):
    consent_confirmed: bool = False
    sample_name: Optional[str] = Field(None, max_length=NAME_MAX_CHARS)


class ReadingContext(BaseModel):
    source_type: str = Field(..., description="current_story")
    game_id: int
    week: Optional[int] = None
    round_number: Optional[int] = None
    stage: Optional[str] = None
    attempt_id: Optional[str] = None
    day_index: Optional[int] = None
    story_date: Optional[str] = None
    text_hash: str
    text: str = Field(..., min_length=1, max_length=VOICE_TEXT_MAX_CHARS)


class StoryVoiceReadingRequest(BaseModel):
    context: ReadingContext
    voice_id: str = "warm_female"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    auto_play: bool = False


class VoiceReadingSegmentResponse(BaseModel):
    paragraph_index: int
    status: str
    audio_url: Optional[str] = None
    asset_id: Optional[int] = None
    duration_ms: Optional[int] = None
    media_type: Optional[str] = None
    error_code: Optional[str] = None


class StoryVoiceReadingResponse(BaseModel):
    job_id: int
    status: str
    audio_url: Optional[str] = None
    asset_id: Optional[int] = None
    duration_ms: Optional[int] = None
    playback_mode: str = "unavailable"
    provider: str = "minimax"
    model: str = ""
    media_type: Optional[str] = None
    error_code: Optional[str] = None
    message: str = ""
    segments: List[VoiceReadingSegmentResponse] = Field(default_factory=list)


class VoiceReadingJobResponse(BaseModel):
    job_id: int
    status: str
    audio_url: Optional[str] = None
    asset_id: Optional[int] = None
    duration_ms: Optional[int] = None
    playback_mode: str = "unavailable"
    provider: str = "minimax"
    model: str = ""
    media_type: Optional[str] = None
    error_code: Optional[str] = None
    message: str = ""
    segments: List[VoiceReadingSegmentResponse] = Field(default_factory=list)


class VoiceReadingProgressRequest(BaseModel):
    game_id: int
    day_index: int = Field(ge=0)
    story_date: Optional[str] = None
    text_hash: str = Field(min_length=1, max_length=128)
    voice_id: str
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    paragraph_index: int = Field(default=0, ge=0)
    position_ms: int = Field(default=0, ge=0)
    completed: bool = False


class VoiceReadingProgressResponse(VoiceReadingProgressRequest):
    updated_at: Optional[str] = None


class VoiceAssetResponse(BaseModel):
    asset_id: int
    source_type: str
    text_hash: str
    voice_id: str
    provider: str
    model: str
    storage_path: str
    duration_ms: int
    status: str


class StoryVoiceErrorResponse(BaseModel):
    error_code: str
    message: str
    field: Optional[str] = None


# ==================== Story Adjustment ====================


class RewriteStoryRequest(BaseModel):
    full_story: str = Field(..., max_length=FULL_STORY_MAX_CHARS)
    segment_to_replace: Optional[str] = Field(
        None, max_length=REPLACEMENT_SEGMENT_MAX_CHARS
    )
    user_instruction: str = Field(..., max_length=STORY_REWRITE_INSTRUCTION_MAX_CHARS)
    language: str = "zh"


class RegenerateStoryRequest(BaseModel):
    language: str = "zh"


class StoryChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=STORY_DIALOGUE_MAX_CHARS)
    language: str = "zh"


class StoryChatResponse(BaseModel):
    reply: str


# ==================== Generic ====================


class MessageResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[Dict[str, Any]] = None


# ==================== Image Generation ====================


class GenerateImageRequest(BaseModel):
    """生成图片请求"""

    game_id: int
    image_type: str = Field(..., description="character|location|item")
    entity_name: str = Field(
        ..., max_length=NAME_MAX_CHARS, description="人物名/地点名/物品名"
    )
    description: str = Field(..., description="描述文本")
    entity_key: Optional[str] = Field(None, description="实体唯一标识")
    era: str = Field(default="现代", description="时代背景")
    extra_context: Optional[CharacterSettingsPayload] = Field(None, description="额外上下文")
    feedback: Optional[str] = Field(
        None, max_length=FEEDBACK_MAX_CHARS, description="重新生成时的修改意见"
    )


class RegenerateImageRequest(BaseModel):
    """重新生成图片请求"""

    image_id: int
    feedback: Optional[str] = Field(
        None, max_length=FEEDBACK_MAX_CHARS, description="修改意见"
    )
    new_description: Optional[str] = Field(None, description="新描述")


class RegenerateFreshImageRequest(BaseModel):
    """完全重新生成图片请求（抛弃历史修改）"""

    image_id: int
    use_deepseek_prompt: bool = Field(True, description="是否使用DeepSeek生成优化prompt")


class BatchGenerateCharactersRequest(BaseModel):
    """批量生成关键人物画像请求"""

    game_id: int
    character_settings: CharacterSettingsPayload = Field(
        ..., description="角色设定（包含family和relationships）"
    )
    language: str = Field(default="zh", description="语言")


class ImageResponse(BaseModel):
    """图片响应"""

    image_id: int
    game_id: int
    image_type: str
    entity_name: str
    entity_key: Optional[str] = None
    image_url: str
    prompt_used: str
    version: int = 1
    created_at: Optional[str] = None


class ImageListResponse(BaseModel):
    """图片列表响应"""

    images: List[ImageResponse]
    total: int


class PortraitImageGenerationJobResponse(BaseModel):
    """Safe public state for a durable main-character portrait job."""

    job_id: int
    game_id: int
    status: str
    image_id: Optional[int] = None
    attempt_count: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==================== Save Points (时间回溯) ====================


class CreateSavePointRequest(BaseModel):
    """创建存档点请求"""

    save_name: Optional[str] = Field(
        None, max_length=NAME_MAX_CHARS, description="存档名称（可选）"
    )


class SavePointItem(BaseModel):
    """存档点信息"""

    state_id: int
    game_id: int
    week: int
    age: int
    save_name: Optional[str] = None
    created_at: Optional[str] = None
    player_name: str = "未命名"
    is_save_point: bool = True


class SavePointListResponse(BaseModel):
    """存档点列表响应"""

    game_id: int
    player_name: str
    save_points: List[SavePointItem]
    total: int


class StateSnapshotItem(BaseModel):
    """状态快照信息（包括自动快照和手动存档）"""

    state_id: int
    game_id: int
    week: int
    age: int
    is_save_point: bool
    save_name: Optional[str] = None
    created_at: Optional[str] = None
    player_name: str = "未命名"


class StateTimelineResponse(BaseModel):
    """状态时间线响应"""

    game_id: int
    player_name: str
    snapshots: List[StateSnapshotItem]
    total: int


# ==================== Opening Illustration ====================


class GenerateOpeningIllustrationRequest(BaseModel):
    """生成开场插画请求"""

    game_id: int
    story_text: str = Field(..., max_length=FULL_STORY_MAX_CHARS, description="开场故事文本")
    character_settings: CharacterSettingsPayload = Field(default_factory=dict, description="角色设定")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")
    player_name: str = Field(..., max_length=NAME_MAX_CHARS, description="角色姓名")


class OpeningIllustrationResponse(BaseModel):
    """开场插画响应"""

    image_id: int
    game_id: int
    image_url: str
    scene_description: str = Field(..., description="DeepSeek选择的场景描述")
    prompt_used: str = Field(..., description="生成时使用的提示词")
    created_at: Optional[str] = None


class RegenerateOpeningIllustrationRequest(BaseModel):
    """重新生成开场插画请求"""

    game_id: int
    story_text: str = Field(..., max_length=FULL_STORY_MAX_CHARS, description="开场故事文本")
    character_settings: CharacterSettingsPayload = Field(default_factory=dict, description="角色设定")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")
    player_name: str = Field(..., max_length=NAME_MAX_CHARS, description="角色姓名")
    user_prompt: str = Field(..., max_length=FEEDBACK_MAX_CHARS, description="用户自定义提示词/修改意见")
    current_illustration_id: int = Field(..., description="当前插画ID，作为参考")


class RegenerateRoundSceneRequest(BaseModel):
    """重新生成每轮场景插画请求"""

    game_id: int
    round_number: int = Field(..., description="轮次")
    story_text: str = Field(..., max_length=FULL_STORY_MAX_CHARS, description="该轮的故事文本")
    character_settings: CharacterSettingsPayload = Field(default_factory=dict, description="角色设定")
    player_name: str = Field(..., max_length=NAME_MAX_CHARS, description="角色姓名")
    user_prompt: str = Field(..., max_length=FEEDBACK_MAX_CHARS, description="用户自定义提示词/修改意见")
    current_scene_id: int = Field(..., description="当前场景插画ID，作为参考")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")
    story_date: Optional[str] = None
    day_index: Optional[int] = Field(default=None, ge=0)


class GenerateRoundSceneRequest(BaseModel):
    """自动生成每轮场景插画请求"""

    game_id: int
    week: Optional[int] = Field(None, description="周数（可选，不传则自动从数据库获取）")
    round_number: int = Field(..., description="轮次")
    story_text: str = Field(..., max_length=FULL_STORY_MAX_CHARS, description="该轮的故事文本")
    character_settings: CharacterSettingsPayload = Field(default_factory=dict, description="角色设定")
    player_name: str = Field(..., max_length=NAME_MAX_CHARS, description="角色姓名")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")
    stage: str = Field("result", description="场景阶段: event(事件故事) 或 result(结果故事)")
    story_date: Optional[str] = None
    day_index: Optional[int] = Field(default=None, ge=0)


class RoundSceneResponse(BaseModel):
    """场景插画响应"""

    scene_id: int
    game_id: int
    week: int = 0  # ★ 新增：周数
    round_number: int
    story_date: Optional[str] = None
    day_index: Optional[int] = None
    stage: str = "result"  # ★ 场景阶段
    image_url: str
    scene_description: str
    created_at: Optional[str] = None


# ==================== Collection (收集系统) ====================


class CharacterCollectionItem(BaseModel):
    """人物收集项"""

    name: str
    role: str = ""
    description: str = ""
    affinity: int = 50
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    personality_traits: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    image_generated: bool = False
    description_generated: bool = False


class ItemCollectionItem(BaseModel):
    """物品收集项"""

    name: str
    description: str = ""
    importance: str = "normal"  # critical/important/normal
    category: str = "other"  # weapon/tool/keepsake/treasure/document/other
    acquired_week: int = 0
    acquired_context: str = ""
    is_key_item: bool = False
    image_url: Optional[str] = None
    image_generated: bool = False
    description_generated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LandmarkCollectionItem(BaseModel):
    """标志物收集项"""

    name: str
    description: str = ""
    category: str = "other"  # building/nature/room/area/other
    importance: str = "normal"  # critical/important/normal
    first_appear_week: int = 0
    appear_count: int = 1
    last_appear_week: int = 0
    context: str = ""
    is_key_location: bool = False
    image_url: Optional[str] = None
    image_generated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CollectionResponse(BaseModel):
    """收集数据响应"""

    game_id: int
    characters: List[CharacterCollectionItem]
    items: List[ItemCollectionItem]
    landmarks: List[LandmarkCollectionItem] = Field(default_factory=list)
    total_characters: int
    total_items: int
    total_landmarks: int = 0


class RegenerateCharacterImageRequest(BaseModel):
    """重新生成人物画像请求"""

    feedback: str = Field(..., max_length=FEEDBACK_MAX_CHARS, description="用户修改意见，例如：头发变长一点、换一件蓝色衣服")
    image_id: Optional[int] = Field(
        None, description="可选：指定要修改的图片ID，不传则使用当前活跃图片"
    )


class RegenerateItemImageRequest(BaseModel):
    """重新生成物品图片请求"""

    feedback: str = Field(..., max_length=FEEDBACK_MAX_CHARS, description="用户修改意见")


# ==================== Entity Recognition (实体识别) ====================


class EntityRecognitionRequest(BaseModel):
    """实体识别请求"""

    entity_types: List[str] = Field(
        default_factory=lambda: ["item", "character", "landmark"],
        description="要识别的实体类型",
    )
    min_appearances: int = Field(default=3, ge=1, le=10, description="最少出现次数")


class RecognizedEntity(BaseModel):
    """识别出的实体"""

    name: str = Field(..., description="实体名称")
    description: str = Field(..., description="详细描述")
    category: str = Field(default="other", description="类别")
    importance: str = Field(default="normal", description="重要程度")
    appear_count: int = Field(default=1, description="出现次数")
    appear_contexts: List[str] = Field(default_factory=list, description="出现的上下文片段")


class RecognizedEntityWrite(BaseModel):
    """New entity write payload; response and stored entity models stay permissive."""

    name: str = Field(..., max_length=NAME_MAX_CHARS, description="实体名称")
    description: str = Field(..., description="详细描述")
    category: str = Field(default="other", description="类别")
    importance: str = Field(default="normal", description="重要程度")
    appear_count: int = Field(default=1, description="出现次数")
    appear_contexts: List[str] = Field(default_factory=list, description="出现的上下文片段")


class EntityRecognitionResponse(BaseModel):
    """实体识别响应"""

    items: List[RecognizedEntity] = Field(default_factory=list)
    characters: List[RecognizedEntity] = Field(default_factory=list)
    landmarks: List[RecognizedEntity] = Field(default_factory=list)


class AddEntitiesRequest(BaseModel):
    """批量添加实体请求"""

    items: List[RecognizedEntityWrite] = Field(default_factory=list)
    characters: List[RecognizedEntityWrite] = Field(default_factory=list)
    landmarks: List[RecognizedEntityWrite] = Field(default_factory=list)


class AddEntitiesResponse(BaseModel):
    """批量添加实体响应"""

    message: str = ""
    success: bool = True
    added_items: List[str] = Field(default_factory=list)
    added_characters: List[str] = Field(default_factory=list)
    added_landmarks: List[str] = Field(default_factory=list)


class CreateItemRequest(BaseModel):
    """手动创建物品请求"""

    name: str = Field(
        ..., min_length=1, max_length=NAME_MAX_CHARS, description="物品名称"
    )
    generate_description: bool = Field(default=True, description="是否从历史中生成描述")


class CreateItemResponse(BaseModel):
    """手动创建物品响应"""

    message: str = ""
    success: bool = True
    item: Optional[ItemCollectionItem] = None
