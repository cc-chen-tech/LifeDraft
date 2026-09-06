"""MiniMax system voice catalog used by the story-reader selector."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MiniMaxVoice:
    voice_id: str
    label: str
    language: str
    group: str
    recommended: bool = False


# Keep legacy aliases at the top while exposing real MiniMax IDs to new users.
_CURATED_VOICES: tuple[MiniMaxVoice, ...] = (
    MiniMaxVoice("female-shaonv", "少女·灵动", "中文", "故事推荐", True),
    MiniMaxVoice("male-qn-qingse", "青年·清朗", "中文", "故事推荐", True),
    MiniMaxVoice("female-yujie", "御姐·沉稳", "中文", "故事推荐", True),
    MiniMaxVoice("male-qn-jingying", "青年·精英", "中文", "中文", False),
    MiniMaxVoice("female-chengshu", "成熟女声", "中文", "中文", False),
    MiniMaxVoice("male-qn-badao", "霸道青年", "中文", "中文", False),
    MiniMaxVoice("English_Trustworthy_Man", "Trustworthy Man", "English", "English", False),
    MiniMaxVoice("English_CalmWoman", "Calm Woman", "English", "English", False),
    MiniMaxVoice("English_CaptivatingStoryteller", "Captivating Storyteller", "English", "English", True),
    MiniMaxVoice("Japanese_CalmLady", "Calm Lady", "日本語", "日本語", False),
    MiniMaxVoice("Korean_SweetGirl", "Sweet Girl", "한국어", "한국어", False),
)

# The official page is a catalog, not a stable API endpoint. Keep the IDs in
# source so the UI can search/select them without making a provider request.
# Curated entries above carry human labels; these additional official IDs use
# their provider names as labels and are grouped by the language prefix.
_ADDITIONAL_SYSTEM_VOICE_IDS = """
female-shaonv-jingpin female-tianmei female-tianmei-jingpin female-yujie-jingpin
male-qn-badao-jingpin male-qn-daxuesheng male-qn-daxuesheng-jingpin male-qn-jingying-jingpin male-qn-qingse-jingpin
English_Aussie_Bloke English_Diligent_Man English_Gentle-voiced_man English_Graceful_Lady English_Whispering_girl
Arabic_CalmWoman Arabic_FriendlyGuy Cantonese_CuteGirl Cantonese_GentleLady Cantonese_KindWoman Cantonese_PlayfulMan Cantonese_ProfessionalHost
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

_CURATED_IDS = {voice.voice_id for voice in _CURATED_VOICES}
MINIMAX_VOICES: tuple[MiniMaxVoice, ...] = _CURATED_VOICES + tuple(
    MiniMaxVoice(
        voice_id=voice_id,
        label=voice_id,
        language=voice_id.split("_", 1)[0] if "_" in voice_id else "中文",
        group="全部音色库",
    )
    for voice_id in _ADDITIONAL_SYSTEM_VOICE_IDS
    if voice_id not in _CURATED_IDS
)

LEGACY_VOICE_ALIASES = {
    "warm_female": "female-shaonv",
    "calm_male": "male-qn-qingse",
    "clear_neutral": "female-yujie",
}


def voice_options(query: str = "", *, include_legacy: bool = False) -> list[dict[str, Any]]:
    normalized = query.strip().lower()
    voices: Iterable[MiniMaxVoice] = MINIMAX_VOICES
    if include_legacy:
        voices = tuple(voices) + tuple(
            MiniMaxVoice(alias, f"兼容 · {alias}", "中文", "兼容旧设置")
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


def preview_text_for_voice(voice_id: str) -> str:
    """Return a short neutral sentence suitable for an on-demand preview."""
    canonical = canonical_voice_id(voice_id)
    voice = next((item for item in MINIMAX_VOICES if item.voice_id == canonical), None)
    if voice is None or voice.language == "中文":
        return "夜色渐深，故事才刚刚开始。"
    if voice.language == "日本語":
        return "夜が更けても、物語は始まったばかりです。"
    if voice.language == "한국어":
        return "밤이 깊어도 이야기는 이제 막 시작되었습니다."
    return "The night grows quiet, but the story is only beginning."
