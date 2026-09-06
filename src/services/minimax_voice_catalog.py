"""MiniMax system voices exposed by the Chinese story reader."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Collection, Iterable, Optional


@dataclass(frozen=True)
class MiniMaxVoice:
    voice_id: str
    label: str
    language: str
    group: str
    recommended: bool = False


DEFAULT_STORY_VOICE_ID = "female-shaonv"
STORY_VOICE_LANGUAGES = ("普通话", "粤语")


# These names and IDs mirror MiniMax's official Chinese system voice table.
# ``label`` is the only user-facing name; IDs remain provider implementation
# details and are never used to build UI copy.
_CHINESE_VOICES: tuple[MiniMaxVoice, ...] = (
    MiniMaxVoice("male-qn-qingse", "青涩青年音色", "普通话", "标准音色", True),
    MiniMaxVoice("male-qn-jingying", "精英青年音色", "普通话", "标准音色", False),
    MiniMaxVoice("male-qn-badao", "霸道青年音色", "普通话", "标准音色", False),
    MiniMaxVoice("male-qn-daxuesheng", "青年大学生音色", "普通话", "标准音色", False),
    MiniMaxVoice("female-shaonv", "少女音色", "普通话", "标准音色", True),
    MiniMaxVoice("female-yujie", "御姐音色", "普通话", "标准音色", True),
    MiniMaxVoice("female-chengshu", "成熟女性音色", "普通话", "标准音色", True),
    MiniMaxVoice("female-tianmei", "甜美女性音色", "普通话", "标准音色", False),
    MiniMaxVoice("male-qn-qingse-jingpin", "青涩青年音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("male-qn-jingying-jingpin", "精英青年音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("male-qn-badao-jingpin", "霸道青年音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("male-qn-daxuesheng-jingpin", "青年大学生音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("female-shaonv-jingpin", "少女音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("female-yujie-jingpin", "御姐音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("female-chengshu-jingpin", "成熟女性音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("female-tianmei-jingpin", "甜美女性音色 · 精品版", "普通话", "精品音色", False),
    MiniMaxVoice("clever_boy", "聪明男童", "普通话", "角色音色", False),
    MiniMaxVoice("cute_boy", "可爱男童", "普通话", "角色音色", False),
    MiniMaxVoice("lovely_girl", "萌萌女童", "普通话", "角色音色", False),
    MiniMaxVoice("cartoon_pig", "卡通猪小琪", "普通话", "角色音色", False),
    MiniMaxVoice("bingjiao_didi", "病娇弟弟", "普通话", "角色音色", False),
    MiniMaxVoice("junlang_nanyou", "俊朗男友", "普通话", "角色音色", False),
    MiniMaxVoice("chunzhen_xuedi", "纯真学弟", "普通话", "角色音色", False),
    MiniMaxVoice("lengdan_xiongzhang", "冷淡学长", "普通话", "角色音色", False),
    MiniMaxVoice("badao_shaoye", "霸道少爷", "普通话", "角色音色", False),
    MiniMaxVoice("tianxin_xiaoling", "甜心小玲", "普通话", "角色音色", False),
    MiniMaxVoice("qiaopi_mengmei", "俏皮萌妹", "普通话", "角色音色", False),
    MiniMaxVoice("wumei_yujie", "妩媚御姐", "普通话", "角色音色", False),
    MiniMaxVoice("diadia_xuemei", "嗲嗲学妹", "普通话", "角色音色", False),
    MiniMaxVoice("danya_xuejie", "淡雅学姐", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Reliable_Executive", "沉稳高管", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_News_Anchor", "新闻女声", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Mature_Woman", "傲娇御姐", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Unrestrained_Young_Man", "不羁青年", "普通话", "主播与叙事", False),
    MiniMaxVoice("Arrogant_Miss", "嚣张小姐", "普通话", "角色音色", False),
    MiniMaxVoice("Robot_Armor", "机械战甲", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Kind-hearted_Antie", "热心大婶", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_HK_Flight_Attendant", "港普空姐", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Humorous_Elder", "搞笑大爷", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Gentleman", "温润男声", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Warm_Bestie", "温暖闺蜜", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Male_Announcer", "播报男声", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Sweet_Lady", "甜美女声", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Southern_Young_Man", "南方小哥", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Wise_Women", "阅历姐姐", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Gentle_Youth", "温润青年", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Warm_Girl", "温暖少女", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Kind-hearted_Elder", "花甲奶奶", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Cute_Spirit", "憨憨萌兽", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Radio_Host", "电台男主播", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Lyrical_Voice", "抒情男声", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Straightforward_Boy", "率真弟弟", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Sincere_Adult", "真诚青年", "普通话", "主播与叙事", False),
    MiniMaxVoice("Chinese (Mandarin)_Gentle_Senior", "温柔学姐", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Stubborn_Friend", "嘴硬竹马", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Crisp_Girl", "清脆少女", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Pure-hearted_Boy", "清澈邻家弟弟", "普通话", "角色音色", False),
    MiniMaxVoice("Chinese (Mandarin)_Soft_Girl", "柔和少女", "普通话", "角色音色", False),
    MiniMaxVoice("Cantonese_ProfessionalHost（F)", "专业女主持", "粤语", "粤语音色", False),
    MiniMaxVoice("Cantonese_GentleLady", "温柔女声", "粤语", "粤语音色", False),
    MiniMaxVoice("Cantonese_ProfessionalHost（M)", "专业男主持", "粤语", "粤语音色", False),
    MiniMaxVoice("Cantonese_PlayfulMan", "活泼男声", "粤语", "粤语音色", False),
    MiniMaxVoice("Cantonese_CuteGirl", "可爱女孩", "粤语", "粤语音色", False),
    MiniMaxVoice("Cantonese_KindWoman", "善良女声", "粤语", "粤语音色", False),
)


# Keep provider-level support for the other official IDs so old assets and
# MiniMax provider validation remain compatible. Story settings use the
# Chinese-only filter below and never return these entries to the UI.
_ADDITIONAL_SYSTEM_VOICE_IDS = """
English_Trustworthy_Man English_CalmWoman English_CaptivatingStoryteller English_Aussie_Bloke English_Diligent_Man English_Gentle-voiced_man English_Graceful_Lady English_Whispering_girl
Arabic_CalmWoman Arabic_FriendlyGuy Korean_SweetGirl Cantonese_ProfessionalHost
French_CasualMan French_FemaleAnchor French_Female_News French_MaleNarrator French_Male_Speech_New French_MovieLeadFemale
German_FriendlyMan German_PlayfulMan German_SweetLady
Indonesian_BossyLeader Indonesian_CalmWoman Indonesian_CaringMan Indonesian_CharmingGirl Indonesian_ConfidentWoman Indonesian_DeterminedBoy Indonesian_GentleGirl Indonesian_ReservedYoungMan Indonesian_SweetGirl
Italian_BraveHeroine Italian_DiligentLeader Italian_Narrator Italian_WanderingSorcerer
Japanese_CalmLady Japanese_ColdQueen Japanese_DecisivePrincess Japanese_DependableWoman Japanese_DominantMan Japanese_GenerousIzakayaOwner Japanese_GentleButler Japanese_GracefulMaiden Japanese_InnocentBoy Japanese_IntellectualSenior Japanese_KindLady Japanese_LoyalKnight Japanese_OptimisticYouth Japanese_SeriousCommander Japanese_SportyStudent
Korean_AirheadedGirl Korean_AthleticGirl Korean_AthleticStudent Korean_BraveAdventurer Korean_BraveFemaleWarrior Korean_BraveYouth Korean_CalmGentleman Korean_CalmLady Korean_CaringWoman Korean_CharmingElderSister Korean_CharmingSister Korean_CheerfulBoyfriend Korean_CheerfulCoolJunior Korean_CheerfulLittleSister Korean_ChildhoodFriendGirl Korean_CockyGuy Korean_ColdGirl Korean_ColdYoungMan Korean_ConfidentBoss Korean_ConsiderateSenior Korean_DecisiveQueen Korean_DominantMan Korean_ElegantPrincess Korean_EnchantingSister Korean_EnthusiasticTeen Korean_FriendlyBigSister Korean_GentleBoss Korean_GentleWoman Korean_HaughtyLady Korean_InnocentBoy Korean_IntellectualMan Korean_IntellectualSenior Korean_LonelyWarrior Korean_MatureLady Korean_MysteriousGirl Korean_OptimisticYouth Korean_PlayboyCharmer Korean_PossessiveMan Korean_QuirkyGirl Korean_ReliableSister Korean_ReliableYouth Korean_SassyGirl Korean_ShyGirl Korean_SoothingLady Korean_StrictBoss Korean_ThoughtfulWoman Korean_WiseElf Korean_WiseTeacher
Russian_AmbitiousWoman Russian_AttractiveGuy Russian_Bad-temperedBoy Russian_BrightHeroine Russian_CrazyQueen Russian_HandsomeChildhoodFriend Russian_PessimisticGirl Russian_ReliableMan
Spanish_AngryMan Spanish_AnimeCharacter Spanish_Arnold Spanish_AssertiveQueen Spanish_BossyLeader Spanish_CaptivatingStoryteller Spanish_CaringGirlfriend Spanish_ChattyGirl Spanish_Comedian Spanish_CompellingGirl Spanish_ConfidentWoman Spanish_Debator Spanish_Deep-tonedMan Spanish_DeterminedManager Spanish_EnergeticBoy Spanish_FrankLady Spanish_Fussyhostess Spanish_Ghost Spanish_HumorousElder Spanish_Intonategirl Spanish_Jovialman Spanish_Kind-heartedGirl Spanish_MaturePartner Spanish_Narrator Spanish_PassionateWarrior Spanish_PowerfulSoldier Spanish_PowerfulVeteran Spanish_RationalMan Spanish_ReliableMan Spanish_ReservedYoungMan Spanish_RomanticHusband Spanish_Rudolph Spanish_SantaClaus Spanish_SensibleManager Spanish_SereneElder Spanish_SereneWoman Spanish_SincereTeen Spanish_SophisticatedLady Spanish_Steadymentor Spanish_StrictBoss Spanish_Strong-WilledBoy Spanish_ThoughtfulLady Spanish_ThoughtfulMan Spanish_ToughBoss Spanish_WhimsicalGirl Spanish_WiseScholar Spanish_Wiselady
Portuguese_AngryMan Portuguese_AnimeCharacter Portuguese_Arnold Portuguese_AssertiveQueen Portuguese_BossyLeader Portuguese_CalmLeader Portuguese_CaptivatingStoryteller Portuguese_CaringGirlfriend Portuguese_CharmingLady Portuguese_CharmingQueen Portuguese_CharmingSanta Portuguese_ChattyGirl Portuguese_Comedian Portuguese_CompellingGirl Portuguese_ConfidentWoman Portuguese_Conscientiousinstructor Portuguese_Debator Portuguese_Deep-VoicedGentleman Portuguese_DeterminedManager Portuguese_Dramatist Portuguese_ElegantGirl Portuguese_EnergeticBoy Portuguese_FascinatingBoy Portuguese_FragileBoy Portuguese_FrankLady Portuguese_FriendlyNeighbor Portuguese_Fussyhostess Portuguese_GentleTeacher Portuguese_Ghost Portuguese_Godfather Portuguese_GorgeousLady Portuguese_GrimReaper Portuguese_Grinch Portuguese_HumorousElder Portuguese_InspiringLady Portuguese_Jovialman Portuguese_Kind-heartedGirl Portuguese_LovelyLady Portuguese_MaturePartner Portuguese_Narrator Portuguese_NaughtySchoolgirl Portuguese_PassionateWarrior Portuguese_PlayfulGirl Portuguese_PlayfulSpirit Portuguese_Pompouslady Portuguese_PowerfulSoldier Portuguese_PowerfulVeteran Portuguese_RationalMan Portuguese_ReliableMan Portuguese_ReservedYoungMan Portuguese_RomanticHusband Portuguese_Rudolph Portuguese_SadTeen Portuguese_SantaClaus Portuguese_SensibleManager Portuguese_SentimentalLady Portuguese_SereneElder Portuguese_SereneWoman Portuguese_SmartYoungGirl Portuguese_Steadymentor Portuguese_StrictBoss Portuguese_Strong-WilledBoy Portuguese_SweetGirl Portuguese_TheatricalActor Portuguese_ThoughtfulLady Portuguese_ThoughtfulMan Portuguese_ToughBoss Portuguese_UpsetGirl Portuguese_WhimsicalGirl Portuguese_WiseScholar Portuguese_Wiselady
Thai_female_1_sample1 Thai_female_2_sample2 Thai_male_1_sample8 Thai_male_2_sample2 Turkish_CalmWoman Turkish_Trustworthyman Vietnamese_kindhearted_girl
""".split()

_CHINESE_IDS = {voice.voice_id for voice in _CHINESE_VOICES}
MINIMAX_VOICES: tuple[MiniMaxVoice, ...] = _CHINESE_VOICES + tuple(
    MiniMaxVoice(
        voice_id=voice_id,
        label=voice_id,
        language=voice_id.split("_", 1)[0] if "_" in voice_id else "未知",
        group="其他语言",
    )
    for voice_id in _ADDITIONAL_SYSTEM_VOICE_IDS
    if voice_id not in _CHINESE_IDS
)

LEGACY_VOICE_ALIASES = {
    "warm_female": "female-shaonv",
    "calm_male": "male-qn-qingse",
    "clear_neutral": "female-yujie",
}


def voice_options(
    query: str = "",
    *,
    languages: Optional[Collection[str]] = STORY_VOICE_LANGUAGES,
    include_legacy: bool = False,
) -> list[dict[str, Any]]:
    """Return display-ready voices, filtered to story languages by default."""
    normalized = query.strip().lower()
    voices: Iterable[MiniMaxVoice] = tuple(
        voice
        for voice in MINIMAX_VOICES
        if languages is None or voice.language in languages
    )
    if include_legacy:
        voices = tuple(voices) + tuple(
            MiniMaxVoice(alias, f"兼容 · {alias}", "普通话", "兼容旧设置")
            for alias in LEGACY_VOICE_ALIASES
        )
    if normalized:
        voices = (
            voice
            for voice in voices
            if normalized in voice.voice_id.lower()
            or normalized in voice.label.lower()
            or normalized in voice.language.lower()
            or normalized in voice.group.lower()
        )
    return [asdict(voice) for voice in voices]


def canonical_voice_id(voice_id: str) -> str:
    return LEGACY_VOICE_ALIASES.get(voice_id, voice_id)


def is_supported_voice(voice_id: str) -> bool:
    canonical = canonical_voice_id(voice_id)
    return canonical in {voice.voice_id for voice in MINIMAX_VOICES}


def is_story_voice_supported(voice_id: str) -> bool:
    """Return whether an ID is selectable in the Chinese story reader."""
    return canonical_voice_id(voice_id) in _CHINESE_IDS


def normalize_story_voice_id(voice_id: Optional[str]) -> str:
    """Map legacy/missing/non-Chinese settings to the story default."""
    canonical = canonical_voice_id(voice_id or DEFAULT_STORY_VOICE_ID)
    return canonical if is_story_voice_supported(canonical) else DEFAULT_STORY_VOICE_ID


def preview_text_for_voice(voice_id: str) -> str:
    """Return a short neutral sentence suitable for an on-demand preview."""
    canonical = canonical_voice_id(voice_id)
    voice = next((item for item in MINIMAX_VOICES if item.voice_id == canonical), None)
    if voice is None or voice.language in STORY_VOICE_LANGUAGES:
        return "夜色渐深，故事才刚刚开始。"
    if voice.language == "日本語":
        return "夜が更けても、物語は始まったばかりです。"
    if voice.language == "한국어":
        return "밤이 깊어도 이야기는 이제 막 시작되었습니다."
    return "The night grows quiet, but the story is only beginning."
