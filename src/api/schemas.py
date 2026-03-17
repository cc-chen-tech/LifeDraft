"""Pydantic request/response models for all API endpoints."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ==================== Auth ====================


class RegisterRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50)


class LoginRequest(BaseModel):
    private_id: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    token: str
    user: "UserInfo"


class UserInfo(BaseModel):
    user_id: int
    public_id: str
    display_name: Optional[str] = None
    private_id: Optional[str] = None  # Only returned on register


# ==================== Friends ====================


class FriendRequestCreate(BaseModel):
    to_public_id: str = Field(..., min_length=1)


class FriendRequestRespond(BaseModel):
    request_id: int
    accept: bool


class FriendInfo(BaseModel):
    user_id: int
    public_id: str
    display_name: Optional[str] = None


class FriendRequestInfo(BaseModel):
    request_id: int
    from_user: FriendInfo
    created_at: Optional[str] = None


# ==================== Games ====================


class CreateGameRequest(BaseModel):
    character_settings: Dict[str, Any]
    player_name: str
    life_vision: str
    language: str = "zh"


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


class SaveGameResponse(BaseModel):
    success: bool
    message: str = ""


# ==================== Character Creation ====================


class GenerateSettingRequest(BaseModel):
    setting_type: str = Field(
        ..., description="era|age|gender|world|family|relationships|traits|wealth"
    )
    player_name: str
    life_vision: str
    previous_settings: Dict[str, Any] = Field(default_factory=dict)
    feedback: Optional[str] = None
    language: str = "zh"


class GenerateRelationshipRequest(BaseModel):
    player_name: str
    life_vision: str
    previous_settings: Dict[str, Any] = Field(default_factory=dict)
    existing_people: List[Dict[str, Any]] = Field(default_factory=list)
    person_index: int = 0
    total_needed: int = 3
    feedback: Optional[str] = None
    language: str = "zh"


class GenerateAttributesRequest(BaseModel):
    character_settings: Dict[str, Any]
    language: str = "zh"


class OpeningStoryRequest(BaseModel):
    character_settings: Dict[str, Any]
    player_name: str
    life_vision: str
    language: str = "zh"


class RelationshipsSummaryRequest(BaseModel):
    player_name: str
    life_vision: str
    previous_settings: Dict[str, Any] = Field(default_factory=dict)
    key_people: List[Dict[str, Any]] = Field(default_factory=list)
    language: str = "zh"


# ==================== Presets ====================


class CreatePresetRequest(BaseModel):
    preset_name: str = Field(..., min_length=1, max_length=100)
    player_name: str
    life_vision: str = ""
    character_settings: Dict[str, Any] = Field(default_factory=dict)


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


class CustomChoiceRequest(BaseModel):
    custom_text: str = Field(..., min_length=1)


class GenerateSummaryRequest(BaseModel):
    weeks: int = Field(default=10, ge=1)


class ChoiceResultResponse(BaseModel):
    story_continuation: str = ""
    summary: str = ""
    effects_applied: Dict[str, Any] = Field(default_factory=dict)
    need_weekly_summary: bool = False
    weekly_summary: Optional[str] = None
    bonus_effects: Optional[Dict[str, Any]] = None
    game_over: bool = False


# ==================== Story Adjustment ====================


class RewriteStoryRequest(BaseModel):
    full_story: str
    segment_to_replace: Optional[str] = None  # 可选，不提供则改写整个故事
    user_instruction: str
    language: str = "zh"


class RegenerateStoryRequest(BaseModel):
    language: str = "zh"


class StoryChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
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
    entity_name: str = Field(..., description="人物名/地点名/物品名")
    description: str = Field(..., description="描述文本")
    entity_key: Optional[str] = Field(None, description="实体唯一标识")
    era: str = Field(default="现代", description="时代背景")
    extra_context: Optional[Dict[str, Any]] = Field(None, description="额外上下文")
    feedback: Optional[str] = Field(None, description="重新生成时的修改意见")


class RegenerateImageRequest(BaseModel):
    """重新生成图片请求"""

    image_id: int
    feedback: Optional[str] = Field(None, description="修改意见")
    new_description: Optional[str] = Field(None, description="新描述")


class RegenerateFreshImageRequest(BaseModel):
    """完全重新生成图片请求（抛弃历史修改）"""

    image_id: int
    use_deepseek_prompt: bool = Field(True, description="是否使用DeepSeek生成优化prompt")


class BatchGenerateCharactersRequest(BaseModel):
    """批量生成关键人物画像请求"""

    game_id: int
    character_settings: Dict[str, Any] = Field(
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


# ==================== Save Points (时间回溯) ====================


class CreateSavePointRequest(BaseModel):
    """创建存档点请求"""

    save_name: Optional[str] = Field(None, description="存档名称（可选）")


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
    story_text: str = Field(..., description="开场故事文本")
    character_settings: Dict[str, Any] = Field(default_factory=dict, description="角色设定")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")
    player_name: str = Field(..., description="角色姓名")


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
    story_text: str = Field(..., description="开场故事文本")
    character_settings: Dict[str, Any] = Field(default_factory=dict, description="角色设定")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")
    player_name: str = Field(..., description="角色姓名")
    user_prompt: str = Field(..., description="用户自定义提示词/修改意见")
    current_illustration_id: int = Field(..., description="当前插画ID，作为参考")


class RegenerateRoundSceneRequest(BaseModel):
    """重新生成每轮场景插画请求"""

    game_id: int
    round_number: int = Field(..., description="轮次")
    story_text: str = Field(..., description="该轮的故事文本")
    character_settings: Dict[str, Any] = Field(default_factory=dict, description="角色设定")
    player_name: str = Field(..., description="角色姓名")
    user_prompt: str = Field(..., description="用户自定义提示词/修改意见")
    current_scene_id: int = Field(..., description="当前场景插画ID，作为参考")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")


class GenerateRoundSceneRequest(BaseModel):
    """自动生成每轮场景插画请求"""

    game_id: int
    week: Optional[int] = Field(None, description="周数（可选，不传则自动从数据库获取）")
    round_number: int = Field(..., description="轮次")
    story_text: str = Field(..., description="该轮的故事文本")
    character_settings: Dict[str, Any] = Field(default_factory=dict, description="角色设定")
    player_name: str = Field(..., description="角色姓名")
    player_image_id: Optional[int] = Field(None, description="可选：已有的人物图片ID")
    stage: str = Field("result", description="场景阶段: event(事件故事) 或 result(结果故事)")


class RoundSceneResponse(BaseModel):
    """场景插画响应"""

    scene_id: int
    game_id: int
    week: int = 0  # ★ 新增：周数
    round_number: int
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

    feedback: str = Field(..., description="用户修改意见，例如：头发变长一点、换一件蓝色衣服")
    image_id: Optional[int] = Field(
        None, description="可选：指定要修改的图片ID，不传则使用当前活跃图片"
    )


class RegenerateItemImageRequest(BaseModel):
    """重新生成物品图片请求"""

    feedback: str = Field(..., description="用户修改意见")


# ==================== Entity Recognition (实体识别) ====================


class EntityRecognitionRequest(BaseModel):
    """实体识别请求"""

    entity_types: List[str] = Field(
        default_factory=lambda: ["item", "character", "landmark"], description="要识别的实体类型"
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


class EntityRecognitionResponse(BaseModel):
    """实体识别响应"""

    items: List[RecognizedEntity] = Field(default_factory=list)
    characters: List[RecognizedEntity] = Field(default_factory=list)
    landmarks: List[RecognizedEntity] = Field(default_factory=list)


class AddEntitiesRequest(BaseModel):
    """批量添加实体请求"""

    items: List[RecognizedEntity] = Field(default_factory=list)
    characters: List[RecognizedEntity] = Field(default_factory=list)
    landmarks: List[RecognizedEntity] = Field(default_factory=list)


class AddEntitiesResponse(BaseModel):
    """批量添加实体响应"""

    message: str = ""
    success: bool = True
    added_items: List[str] = Field(default_factory=list)
    added_characters: List[str] = Field(default_factory=list)
    added_landmarks: List[str] = Field(default_factory=list)


class CreateItemRequest(BaseModel):
    """手动创建物品请求"""

    name: str = Field(..., min_length=1, max_length=100, description="物品名称")
    generate_description: bool = Field(default=True, description="是否从历史中生成描述")


class CreateItemResponse(BaseModel):
    """手动创建物品响应"""

    message: str = ""
    success: bool = True
    item: Optional[ItemCollectionItem] = None
