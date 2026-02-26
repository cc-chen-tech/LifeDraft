# 故事生成系统升级方案：让故事更像优秀小说

> **文档版本**: v1.0  
> **创建日期**: 2026-02-26  
> **状态**: 待评审

---

## 目录

- [一、背景与目标](#一背景与目标)
- [二、整体架构设计](#二整体架构设计)
- [三、模块一：内驱力与成长弧线](#三模块一内驱力与成长弧线)
- [四、模块二：叙事弧线规划器](#四模块二叙事弧线规划器)
- [五、模块三：情感曲线追踪](#五模块三情感曲线追踪)
- [六、模块四：风格配置器](#六模块四风格配置器)
- [七、模块五：主题演化追踪器](#七模块五主题演化追踪器)
- [八、集成方案](#八集成方案)
- [九、实施路线图](#九实施路线图)
- [十、待讨论事项](#十待讨论事项)

---

## 一、背景与目标

### 1.1 现有系统优势

当前故事生成系统已具备扎实的基础：

| 维度 | 现有能力 |
|------|----------|
| **上下文管理** | 多层上下文注入（角色设定、时间线、历史故事、世界模型） |
| **一致性校验** | 7维度AI校验（地理、职业、性格、时间、承诺、因果、捏造） |
| **世界模型** | 结构化追踪（位置、职业、承诺、因果链、身体状态、行为画像） |
| **两阶段生成** | 故事生成与选项生成分离，故事不受JSON格式约束 |
| **向量检索** | 从历史故事中检索相关片段增强上下文 |

### 1.2 核心缺失

从"写出优秀小说"的角度，系统缺失以下关键能力：

| 缺失维度 | 问题描述 | 影响 |
|----------|----------|------|
| **人物深度** | 角色缺乏内驱力、成长弧线，行为缺乏深层动机支撑 | 人物扁平，读者难以共情 |
| **叙事结构** | 缺乏宏观的叙事节奏规划，故事缺乏起承转合 | 故事松散，缺乏张力 |
| **情感节奏** | 情感强度缺乏追踪和调控，可能持续高潮或平淡 | 读者疲劳或无聊 |
| **风格调性** | 语言风格缺乏控制，每次生成风格不一致 | 缺乏独特"味道" |
| **主题深化** | 故事缺乏主题追踪，思想深度不足 | 故事停留在情节层面 |

### 1.3 升级目标

通过五个模块的叠加，让生成的故事更接近优秀小说的品质：

```
内驱力系统 → 人物有深度
叙事弧线   → 故事有结构
情感曲线   → 情绪有节奏
风格配置   → 语言有特色
主题追踪   → 思想有重量
```

---

## 二、整体架构设计

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PlayerState 扩展                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ InnerDriveState │  │  NarrativeArc   │  │  EmotionCurve   │              │
│  │  (内驱力状态)    │  │  (叙事弧线)      │  │  (情感曲线)      │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐                                   │
│  │  StyleProfile   │  │ ThemeTracker    │                                   │
│  │  (风格配置)      │  │ (主题追踪)       │                                   │
│  └─────────────────┘  └─────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           新增服务层                                         │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐        │
│  │InnerDriveUpdater  │  │ NarrativePlanner  │  │ EmotionAnalyzer   │        │
│  │  (内驱力更新器)    │  │  (叙事规划器)      │  │  (情感分析器)      │        │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘        │
│  ┌───────────────────┐  ┌───────────────────┐                               │
│  │ StyleInjector     │  │ ThemeEvolver      │                               │
│  │  (风格注入器)      │  │  (主题演化器)      │                               │
│  └───────────────────┘  └───────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         现有系统改造点                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ StoryGenerator  │  │ OptionGenerator │  │ConsistencyValid │              │
│  │ +上下文注入      │  │ +内心冲突选项    │  │ +情感/主题维度   │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
游戏开始
    │
    ├─→ InnerDriveUpdater.initialize_from_character_settings()
    │       └─→ 初始化动机、目标、成长阶段、内心冲突
    │
    ├─→ NarrativePlanner.plan_arc()
    │       └─→ 规划叙事弧线、阶段、关键事件
    │
    ├─→ ThemeEvolver.initialize_themes()
    │       └─→ 初始化核心主题
    │
    └─→ StyleProfile 加载/配置
            └─→ 设置写作风格

每周事件生成
    │
    ├─→ 构建提示词时注入：
    │       ├─→ 内驱力上下文
    │       ├─→ 叙事阶段上下文
    │       ├─→ 情感节奏指导
    │       ├─→ 风格要求
    │       └─→ 主题上下文
    │
    └─→ AI生成故事

事件后更新
    │
    ├─→ InnerDriveUpdater.update_from_event()
    │       └─→ 更新动机强度、目标进度、内心冲突、成长阶段
    │
    ├─→ EmotionAnalyzer.analyze_event()
    │       └─→ 记录情感点，更新情感曲线
    │
    ├─→ NarrativePlanner.check_key_event_completion()
    │       └─→ 检查关键事件是否完成
    │
    └─→ ThemeEvolver.analyze_event()
            └─→ 更新主题探索记录
```

---

## 三、模块一：内驱力与成长弧线

> **目标**: 让人物有深层动机，行为有内在逻辑，成长有轨迹可循

### 3.1 核心概念

| 概念 | 说明 | 示例 |
|------|------|------|
| **动机 (Motivation)** | 角色的内在驱动力 | 渴望被认可、恐惧被抛弃、使命感 |
| **目标 (Goal)** | 由动机衍生的具体追求 | 成为团队leader、攒够钱买房 |
| **内心冲突 (InnerConflict)** | 不同动机之间的拉扯 | 想追求自由 vs 放不下家庭责任 |
| **成长阶段 (GrowthStage)** | 人物心理发展的阶段 | 懵懂期 → 觉醒期 → 挣扎期 → 转变期 → 整合期 |
| **关键转变 (TurningPoint)** | 导致价值观质变的事件 | 亲人离世、重大失败、遇见导师 |

### 3.2 数据结构

```python
# src/game/inner_drive/models.py

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class MotivationType(Enum):
    """动机类型"""
    DESIRE = "desire"          # 渴望（追求某事物）
    FEAR = "fear"              # 恐惧（逃避某事物）
    DUTY = "duty"              # 使命/责任
    OBSESSION = "obsession"    # 执念（难以放下的事）
    IDENTITY = "identity"      # 身份认同（想成为什么样的人）


class GrowthStage(Enum):
    """成长阶段"""
    IGNORANCE = "ignorance"        # 懵懂期：不了解自己，随波逐流
    AWAKENING = "awakening"        # 觉醒期：开始意识到内心渴望
    STRUGGLE = "struggle"          # 挣扎期：新旧价值观冲突
    TRANSFORMATION = "transformation"  # 转变期：经历关键事件后改变
    INTEGRATION = "integration"    # 整合期：新的自我形成，内心和谐


class ConflictType(Enum):
    """内心冲突类型"""
    DESIRE_VS_DUTY = "desire_vs_duty"       # 渴望 vs 责任
    FEAR_VS_GROWTH = "fear_vs_growth"       # 恐惧 vs 成长
    OLD_VS_NEW = "old_vs_new"               # 旧我 vs 新我
    SELF_VS_OTHERS = "self_vs_others"       # 自我 vs 他人期待
    SHORT_VS_LONG = "short_vs_long"         # 短期满足 vs 长期目标


@dataclass
class Motivation:
    """动机：角色的内在驱动力"""
    id: str                              # 唯一标识
    type: MotivationType                 # 动机类型
    description: str                     # 描述（如"渴望被认可"）
    source: str                          # 来源（童年经历/某事件/天生性格）
    intensity: float = 0.5               # 强度 0-1（当前对行为的影响程度）
    base_intensity: float = 0.5          # 基础强度（波动基准）
    active: bool = True                  # 是否活跃
    created_week: int = 0                # 形成时间
    last_triggered_week: int = 0         # 上次被触发的周
    trigger_count: int = 0               # 被触发次数


@dataclass
class Goal:
    """目标：由动机衍生的具体目标"""
    id: str                              # 唯一标识
    derived_from: str                    # 衍生自哪个动机ID
    description: str                     # 目标描述
    measurable: bool = True              # 是否可量化
    progress: float = 0.0                # 进度 0-1
    priority: int = 1                    # 优先级 1-5
    status: str = "active"               # active/completed/abandoned/deferred
    target_week: int = -1                # 目标完成周（-1表示无明确期限）
    created_week: int = 0
    completed_week: int = -1
    milestones: List[str] = field(default_factory=list)


@dataclass
class InnerConflict:
    """内心冲突：不同动机之间的拉扯"""
    id: str                              # 唯一标识
    conflict_type: ConflictType          # 冲突类型
    motivation_a_id: str                 # 动机A的ID
    motivation_b_id: str                 # 动机B的ID
    description: str                     # 冲突描述
    tension_level: float = 0.5           # 张力强度 0-1
    resolution_progress: float = 0.0     # 解决进度 0-1
    resolution_type: str = "unresolved"  # unresolved/compromised/a_wins/b_wins/transcended
    active: bool = True
    created_week: int = 0


@dataclass
class TurningPoint:
    """关键转变事件：导致人物价值观或行为模式发生质变的事件"""
    id: str
    week: int                            # 发生周
    event_summary: str                   # 事件摘要
    trigger_type: str                    # crisis/revelation/loss/gift/encounter
    before_state: str                    # 转变前的状态描述
    after_state: str                     # 转变后的状态描述
    affected_motivations: List[str] = field(default_factory=list)
    growth_stage_before: GrowthStage = GrowthStage.IGNORANCE
    growth_stage_after: GrowthStage = GrowthStage.AWAKENING
    significance: float = 0.5            # 重要性 0-1


@dataclass
class InnerDriveState:
    """内驱力状态：完整的人物内心世界"""
    motivations: List[Motivation] = field(default_factory=list)
    goals: List[Goal] = field(default_factory=list)
    current_stage: GrowthStage = GrowthStage.IGNORANCE
    stage_entered_week: int = 0
    turning_points: List[TurningPoint] = field(default_factory=list)
    inner_conflicts: List[InnerConflict] = field(default_factory=list)
    core_values: List[str] = field(default_factory=list)      # 核心价值观
    self_perception: str = ""                                  # 自我认知
    external_expectations: List[str] = field(default_factory=list)  # 他人期待
```

### 3.3 更新器核心逻辑

```python
# src/game/inner_drive/updater.py

class InnerDriveUpdater:
    """内驱力状态更新器"""
    
    def update_from_event(
        self,
        inner_drive_state: InnerDriveState,
        event_description: str,
        player_choice: str,
        outcome: str,
        current_week: int,
        language: str = "zh"
    ) -> InnerDriveState:
        """
        根据事件和玩家选择更新内驱力状态
        
        AI分析输出：
        - motivation_updates: 动机强度变化
        - new_motivations: 新产生的动机
        - goal_updates: 目标进度更新
        - conflict_updates: 冲突张力变化
        - turning_point: 是否触发关键转变
        - growth_stage_transition: 成长阶段是否推进
        """
        pass
    
    def initialize_from_character_settings(
        self,
        character_settings: Dict[str, Any],
        language: str = "zh"
    ) -> InnerDriveState:
        """从角色设定初始化内驱力状态"""
        pass
```

### 3.4 提示词注入示例

```python
def get_inner_drive_context_prompt(inner_drive_state, language: str = "zh") -> str:
    """生成内驱力上下文，用于注入故事生成提示词"""
    
    # 输出示例（中文）：
    """
    【角色内心世界 — 影响行为选择的核心驱动力】
    
    当前成长阶段：觉醒期
    
    核心动机（影响角色决策的内在力量）：
      - 【渴望】被认可、被重视（强度: 75%）
        来源：童年时期父母总是拿自己和别人比较
      - 【恐惧】被抛弃、被遗忘（强度: 60%）
        来源：曾经被好友疏远的经历
      - 【使命】照顾好家人（强度: 50%）
        来源：家庭责任感的培养
    
    内心冲突（角色内心的拉扯，应在故事和选项中体现）：
      - 想追求自己的梦想，但放不下家庭责任（张力: 70%）
    
    当前追求的目标：
      - 在工作中获得一次重要的认可（进度: 30%）
    
    核心价值观：独立、家庭、成长
    
    ⚠️ 写作提示：
      - 故事中应体现角色的核心动机如何影响其行为和选择
      - 如果存在内心冲突，应在故事中展现角色的犹豫和挣扎
      - 选项设计应让玩家面临与动机相关的抉择
    """
```

### 3.5 与选项生成的集成

内心冲突直接影响选项设计：

```python
def get_inner_conflict_options_prompt(inner_drive_state, language: str = "zh") -> str:
    """
    生成内心冲突选项提示
    
    输出示例：
    """
    【选项设计指导 — 内心冲突体现】
    当前角色存在以下内心冲突，请在选项设计中体现：
    
    - 想追求自己的梦想，但放不下家庭责任
      张力强度：70%
    
    选项设计建议：
      - 不同选项可以代表冲突双方的不同倾向
      - 可以设计一个「折中」选项，但应有明显代价
      - 某些选项可能暂时加剧冲突，某些选项可能推动解决
    """
```

---

## 四、模块二：叙事弧线规划器

> **目标**: 让故事有宏观结构，遵循经典叙事节奏

### 4.1 核心概念

| 概念 | 说明 |
|------|------|
| **叙事弧线 (NarrativeArc)** | 整体故事的结构框架 |
| **叙事阶段 (NarrativeStage)** | 弧线中的具体阶段，各有情感基调 |
| **关键事件 (KeyEvent)** | 阶段内必须发生的标志性事件 |

### 4.2 预定义弧线模板

#### 英雄之旅 (Hero's Journey)

```
1. 日常世界 (calm)           → 展示主角的日常生活
2. 冒险召唤 (curious)        → 打破平静的激励事件
3. 拒绝召唤 (hesitant)       → 主角犹豫、抗拒
4. 遇见导师 (hopeful)        → 获得指引
5. 跨越第一道门槛 (determined) → 正式踏上旅程
6. 考验、盟友与敌人 (tense)   → 面对挑战，建立关系
7. 接近最深的洞穴 (anxious)  → 接近核心挑战
8. 磨难 (desperate)          → 最大的考验
9. 奖赏 (relieved)           → 克服后的收获
10. 回归之路 (cautious)      → 带着收获返回
11. 复活 (triumphant)        → 最后的考验
12. 带着万灵药回归 (fulfilled) → 回到日常，但已改变
```

#### 三幕剧 (Three Act)

```
第一幕：铺垫 → 激励事件 → 第一幕高潮
第二幕：前半 → 中点 → 后半 → 一无所有
第三幕：高潮 → 结局
```

#### 成长故事 (Coming of Age)

```
童年/天真期 → 觉醒时刻 → 试探与冒险 → 冲突与挑战 → 关键抉择 → 蜕变 → 新身份确立 → 融入世界
```

### 4.3 数据结构

```python
# src/game/narrative/arc_models.py

class ArcType(Enum):
    """叙事弧线类型"""
    HERO_JOURNEY = "hero_journey"
    THREE_ACT = "three_act"
    COMING_OF_AGE = "coming_of_age"
    TRAGEDY = "tragedy"
    REDEMPTION = "redemption"
    QUEST = "quest"
    RISE_FALL = "rise_fall"
    SLICE_OF_LIFE = "slice_of_life"


@dataclass
class KeyEvent:
    """关键事件节点"""
    event_type: str                     # inciting_incident/ordeal/climax 等
    name: str
    description: str
    target_week_range: tuple            # (min_week, max_week)
    completed: bool = False
    actual_week: int = -1
    actual_event_summary: str = ""


@dataclass
class NarrativeStage:
    """叙事阶段"""
    name: str
    description: str
    target_week_range: tuple
    emotional_tone: str                 # calm/tense/desperate/hopeful 等
    pacing: str = "normal"              # slow/normal/fast
    key_events: List[KeyEvent] = field(default_factory=list)
    narrative_goals: List[str] = field(default_factory=list)
    completed: bool = False


@dataclass
class NarrativeArc:
    """叙事弧线"""
    arc_type: ArcType
    total_weeks: int
    stages: List[NarrativeStage] = field(default_factory=list)
    current_stage_index: int = 0
    deviation_score: float = 0.0        # 偏离原计划的程度
    adjustments: List[str] = field(default_factory=list)
```

### 4.4 规划器核心逻辑

```python
# src/game/narrative/planner.py

class NarrativePlanner:
    """叙事弧线规划器"""
    
    def plan_arc(
        self,
        life_vision: str,
        character_settings: Dict[str, Any],
        total_weeks: int,
        language: str = "zh"
    ) -> NarrativeArc:
        """
        规划叙事弧线
        
        流程：
        1. AI分析适合的弧线类型
        2. 从模板创建基础弧线
        3. AI个性化调整（添加关键事件、叙事目标）
        """
        pass
    
    def check_key_event_completion(
        self,
        arc: NarrativeArc,
        event_description: str,
        current_week: int,
        language: str = "zh"
    ) -> Optional[KeyEvent]:
        """检查事件是否完成了某个关键事件节点"""
        pass
```

### 4.5 提示词注入示例

```python
def get_narrative_arc_context(narrative_arc, current_week: int, language: str = "zh") -> str:
    """生成叙事弧线上下文"""
    
    # 输出示例：
    """
    【叙事结构指导 — 当前所处的故事阶段】
    
    叙事弧线类型：成长故事
    当前阶段：试探与冒险（进度：40%）
    阶段描述：尝试新的身份和行为
    情感基调：excited
    
    本阶段待完成的关键事件：
      - 遇到一个改变观念的人
      - 第一次尝试打破常规
    
    本阶段叙事目标：
      - 展示主角对新可能性的好奇
      - 引入能够影响主角的关键人物
    
    写作提示：
      - 故事节奏可以稍快，体现探索的兴奋感
      - 可以安排一些小冒险或尝试
    """
```

---

## 五、模块三：情感曲线追踪

> **目标**: 让读者情绪有起伏，避免持续高潮或平淡

### 5.1 核心概念

| 概念 | 说明 |
|------|------|
| **情感点 (EmotionPoint)** | 单个事件的情感特征（强度、基调） |
| **情感曲线 (EmotionCurve)** | 情感点的序列，追踪情感变化趋势 |
| **情感节奏调整** | 根据曲线状态调整下一事件的情感强度 |

### 5.2 数据结构

```python
# src/game/emotion/models.py

class EmotionTone(Enum):
    """情感基调"""
    JOY = "joy"                     # 喜悦
    SADNESS = "sadness"             # 悲伤
    FEAR = "fear"                   # 恐惧
    ANGER = "anger"                 # 愤怒
    SURPRISE = "surprise"           # 惊讶
    WARMTH = "warmth"               # 温馨
    HOPE = "hope"                   # 希望
    DESPAIR = "despair"             # 绝望
    PEACE = "peace"                 # 平静
    TENSION = "tension"             # 紧张
    MELANCHOLY = "melancholy"       # 忧郁
    NOSTALGIA = "nostalgia"         # 怀旧


@dataclass
class EmotionPoint:
    """情感曲线上的一个点"""
    week: int
    round: int = 0
    intensity: float = 5.0              # 情感强度 0-10
    primary_tone: EmotionTone = EmotionTone.PEACE
    secondary_tones: List[EmotionTone] = field(default_factory=list)
    source_event: str = ""
    related_characters: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class EmotionCurve:
    """情感曲线"""
    points: List[EmotionPoint] = field(default_factory=list)
    avg_intensity: float = 5.0
    variance: float = 0.0
    consecutive_high_count: int = 0     # 连续高强度周数
    consecutive_low_count: int = 0      # 连续低强度周数
    
    def needs_adjustment(self) -> Optional[str]:
        """判断是否需要调整情感节奏"""
        if self.consecutive_high_count >= 3:
            return "too_intense"        # 需要舒缓
        elif self.consecutive_low_count >= 3:
            return "too_flat"           # 需要戏剧性
        elif self.variance < 1 and len(self.points) >= 5:
            return "monotonous"         # 缺乏变化
        return None
```

### 5.3 情感分析器

```python
# src/game/emotion/analyzer.py

class EmotionAnalyzer:
    """情感分析器"""
    
    def analyze_event(
        self,
        event_description: str,
        player_choice: str,
        outcome: str,
        week: int,
        language: str = "zh"
    ) -> EmotionPoint:
        """
        分析事件的情感特征
        
        AI分析输出：
        - intensity: 情感强度 0-10
        - primary_tone: 主要情感基调
        - secondary_tones: 次要情感基调
        - reasoning: 判断理由
        """
        pass
    
    def get_emotion_guidance(
        self,
        curve: EmotionCurve,
        narrative_stage_tone: str,
        language: str = "zh"
    ) -> str:
        """根据情感曲线生成下一事件的情感指导"""
        pass
```

### 5.4 情感节奏调整示例

```python
def get_emotion_guidance(curve, narrative_stage_tone, language="zh") -> str:
    """根据情感曲线生成指导"""
    
    adjustment = curve.needs_adjustment()
    
    # 输出示例（当需要调整时）：
    """
    【情感节奏指导】
    
    近期平均情感强度：7.8/10
    情感趋势：持续高强度
    
    ⚠️ 情感节奏警告：连续高强度事件
    建议：本周事件应适当舒缓，安排平静的过渡或温馨的日常场景
    避免：重大冲突、危机、激烈的情绪对抗
    """
    
    # 或者：
    """
    【情感节奏指导】
    
    近期平均情感强度：2.3/10
    情感趋势：持续低强度
    
    ⚠️ 情感节奏警告：连续平淡事件
    建议：本周事件应增加戏剧性，引入冲突、意外或重要转折
    可以考虑：突发变故、重要人物出现、关键抉择
    """
```

---

## 六、模块四：风格配置器

> **目标**: 让语言有独特风格，每次生成保持一致调性

### 6.1 核心概念

| 维度 | 选项 | 说明 |
|------|------|------|
| **句式风格** | 简洁/华丽/平衡 | 海明威式 vs 张爱玲式 |
| **对话风格** | 直接/含蓄/混合 | 是否有潜台词 |
| **描写风格** | 极简/细腻/氛围感 | 环境和动作描写的详细程度 |
| **心理描写** | 表层/适度/深入 | 内心独白的深度和比例 |
| **情感表达** | 展示/讲述/混合 | "show, don't tell" 原则 |

### 6.2 数据结构

```python
# src/game/style/models.py

class SentenceStyle(Enum):
    CONCISE = "concise"       # 简洁（海明威式）
    FLOWERY = "flowery"       # 华丽（张爱玲式）
    BALANCED = "balanced"     # 平衡


class DialogueStyle(Enum):
    DIRECT = "direct"         # 直接
    SUBTEXT = "subtext"       # 含蓄有潜台词
    MIXED = "mixed"           # 混合


@dataclass
class StyleProfile:
    """风格配置"""
    name: str = "default"
    
    # 句式风格
    sentence_style: SentenceStyle = SentenceStyle.BALANCED
    avg_sentence_length: int = 20       # 平均句长
    metaphor_density: float = 0.3       # 比喻密度 0-1
    
    # 对话风格
    dialogue_style: DialogueStyle = DialogueStyle.MIXED
    dialogue_ratio: float = 0.35        # 对话占比
    dialogue_subtext_level: float = 0.5  # 潜台词程度
    
    # 描写风格
    description_style: DescriptionStyle = DescriptionStyle.DETAILED
    environment_detail: float = 0.5
    action_detail: float = 0.5
    
    # 心理描写
    psychological_depth: PsychologicalDepth = PsychologicalDepth.MODERATE
    inner_monologue_ratio: float = 0.2
    emotion_expression: str = "show"    # show/tell/mixed
    
    # 风格描述
    description: str = ""
```

### 6.3 预定义风格模板

| 模板名 | 特点 | 适用场景 |
|--------|------|----------|
| **海明威式** | 简洁有力，对话直接，心理描写节制 | 硬汉风格、现实主义 |
| **张爱玲式** | 细腻华丽，比喻丰富，对话含蓄 | 情感细腻、时代剧 |
| **村上春树式** | 疏离氛围，内心独白丰富，都市感 | 现代都市、文艺风 |
| **默认风格** | 平衡的叙事风格 | 通用 |

```python
STYLE_TEMPLATES = {
    "hemingway": StyleProfile(
        name="海明威式",
        sentence_style=SentenceStyle.CONCISE,
        avg_sentence_length=12,
        metaphor_density=0.1,
        dialogue_style=DialogueStyle.DIRECT,
        dialogue_ratio=0.4,
        psychological_depth=PsychologicalDepth.SHALLOW,
        emotion_expression="show",
        description="简洁有力，多用名词和动词，少用形容词。对话直接，心理描写节制。"
    ),
    
    "zhang_ailing": StyleProfile(
        name="张爱玲式",
        sentence_style=SentenceStyle.FLOWERY,
        avg_sentence_length=30,
        metaphor_density=0.6,
        dialogue_style=DialogueStyle.SUBTEXT,
        dialogue_ratio=0.3,
        psychological_depth=PsychologicalDepth.DEEP,
        emotion_expression="mixed",
        description="细腻华丽，善用比喻和意象。对话含蓄有潜台词，心理描写深入。"
    ),
    
    "murakami": StyleProfile(
        name="村上春树式",
        sentence_style=SentenceStyle.BALANCED,
        avg_sentence_length=25,
        metaphor_density=0.4,
        dialogue_style=DialogueStyle.MIXED,
        dialogue_ratio=0.35,
        psychological_depth=PsychologicalDepth.DEEP,
        inner_monologue_ratio=0.25,
        description="疏离而细腻，善于营造氛围。内心独白丰富，常有超现实元素。"
    ),
}
```

### 6.4 风格注入示例

```python
def get_style_prompt(style_profile: StyleProfile, language: str = "zh") -> str:
    """将风格配置转换为提示词"""
    
    # 输出示例（张爱玲式）：
    """
    【写作风格要求】
    
    - 句子可以华丽细腻，善用修辞和意象
    - 平均句长约30字
    - 多用比喻和象征，让抽象情感具体化
    - 对话占比约30%
    - 对话含蓄，有潜台词，角色言外有意
    - 环境和动作描写细腻，有画面感
    - 内心独白占比约30%，深入角色的内心世界
    - 情感用「展示」而非「讲述」，避免直接陈述
    
    细腻华丽，善用比喻和意象。对话含蓄有潜台词，心理描写深入，善于捕捉微妙的情感变化。
    """
```

---

## 七、模块五：主题演化追踪器

> **目标**: 让故事有思想深度，主题在故事中逐步深化

### 7.1 核心概念

| 概念 | 说明 | 示例 |
|------|------|------|
| **主题 (Theme)** | 故事探讨的核心问题 | "自由的代价"、"人性的救赎" |
| **主题探索 (ThemeExploration)** | 单个事件对主题的触及 | 正面印证/反面挑战/复杂化 |
| **探索深度** | 主题被探讨的程度 | 多次、多角度探索后深度增加 |
| **主题高潮** | 主题探索达到顶峰的时刻 | 在关键节点让主题得到最终回答 |

### 7.2 数据结构

```python
# src/game/theme/models.py

class ThemeType(Enum):
    """主题类型"""
    FREEDOM = "freedom"       # 自由
    LOVE = "love"             # 爱
    IDENTITY = "identity"     # 身份认同
    POWER = "power"           # 权力
    MORTALITY = "mortality"   # 死亡与永恒
    REDEMPTION = "redemption" # 救赎
    BELONGING = "belonging"   # 归属
    SACRIFICE = "sacrifice"   # 牺牲
    TRUTH = "truth"           # 真相与谎言
    CHANGE = "change"         # 变化与恒常
    JUSTICE = "justice"       # 正义
    FAMILY = "family"         # 家庭
    AMBITION = "ambition"     # 野心与满足
    ISOLATION = "isolation"   # 孤独与连接


class ThemeStance(Enum):
    """主题立场"""
    AFFIRM = "affirm"           # 正面印证
    CHALLENGE = "challenge"     # 反面挑战
    COMPLICATE = "complicate"   # 复杂化
    TRANSFORM = "transform"     # 转化


@dataclass
class ThemeExploration:
    """主题探索记录"""
    week: int
    event_summary: str
    stance: ThemeStance
    depth: float = 0.5
    insight: str = ""                   # 获得的洞见
    related_characters: List[str] = field(default_factory=list)


@dataclass
class Theme:
    """主题"""
    id: str
    name: str
    theme_type: ThemeType
    description: str = ""
    question: str = ""                  # 主题提出的问题
    explorations: List[ThemeExploration] = field(default_factory=list)
    exploration_depth: float = 0.0
    current_stance: ThemeStance = ThemeStance.COMPLICATE
    related_motivations: List[str] = field(default_factory=list)
    ready_for_climax: bool = False      # 是否为主题高潮做好准备


@dataclass
class ThemeTracker:
    """主题追踪器"""
    themes: List[Theme] = field(default_factory=list)
    primary_theme_id: Optional[str] = None
```

### 7.3 主题演化器

```python
# src/game/theme/evolver.py

class ThemeEvolver:
    """主题演化器"""
    
    def initialize_themes(
        self,
        life_vision: str,
        inner_drive_state: Any,
        language: str = "zh"
    ) -> ThemeTracker:
        """
        初始化主题追踪器
        
        根据人生愿景和核心动机，AI选择1-3个核心主题
        """
        pass
    
    def analyze_event(
        self,
        tracker: ThemeTracker,
        event_description: str,
        player_choice: str,
        week: int,
        language: str = "zh"
    ) -> Optional[ThemeExploration]:
        """
        分析事件与主题的关联
        
        判断事件是否触及主题，以及是正面印证还是反面挑战
        """
        pass
```

### 7.4 主题深化示例

```
主题："自由的代价"

第3周事件：主角为了自由离开家乡
  → 主题触及（正面印证）
  → 洞见：自由需要勇气迈出第一步

第10周事件：主角发现自由带来孤独
  → 主题深化（反面挑战）
  → 洞见：自由的代价是失去归属感

第20周事件：主角在自由与责任之间做出终极选择
  → 主题完成（转化）
  → 洞见：真正的自由是选择自己的责任
```

### 7.5 提示词注入示例

```python
def get_theme_context(tracker: ThemeTracker, language: str = "zh") -> str:
    """生成主题上下文"""
    
    # 输出示例：
    """
    【故事主题 — 思想深度】
    
    核心主题：自由的代价
    主题问题：自由值得付出什么代价？
    探索深度：60%
    
    主题探索历程：
      - 第3周：正面印证（自由需要勇气）
      - 第10周：反面挑战（自由带来孤独）
      - 第15周：复杂化（自由与责任的张力）
    
    ⚠️ 以下主题已准备好进入高潮：
      - 自由的代价
    """
```

---

## 八、集成方案

### 8.1 PlayerState 扩展

```python
# 在 src/game/state/player_state.py 中添加新字段

class PlayerState(BaseModel):
    # ... 现有字段 ...
    
    # ========== 新增：故事深度系统 ==========
    
    # 内驱力状态
    inner_drive_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="内驱力状态：动机、目标、成长阶段、内心冲突"
    )
    
    # 叙事弧线
    narrative_arc: Dict[str, Any] = Field(
        default_factory=dict,
        description="叙事弧线：阶段、关键事件"
    )
    
    # 情感曲线
    emotion_curve: Dict[str, Any] = Field(
        default_factory=dict,
        description="情感曲线：情感强度追踪"
    )
    
    # 风格配置
    style_profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="写作风格配置"
    )
    
    # 主题追踪
    theme_tracker: Dict[str, Any] = Field(
        default_factory=dict,
        description="主题追踪：核心主题及其探索"
    )
```

### 8.2 故事生成集成

在 `config/prompts/story_prompts.py` 的 `get_story_only_prompt` 中添加上下文注入：

```python
def get_story_only_prompt(...) -> str:
    # ... 现有代码 ...
    
    # ★ 新增：内驱力上下文
    inner_drive_context = get_inner_drive_context_prompt(ids, language)
    
    # ★ 新增：叙事弧线上下文
    narrative_context = get_narrative_arc_context(arc, week, language)
    
    # ★ 新增：情感节奏指导
    emotion_guidance = get_emotion_guidance(curve, stage_tone, language)
    
    # ★ 新增：风格配置
    style_context = get_style_prompt(style, language)
    
    # ★ 新增：主题上下文
    theme_context = get_theme_context(tracker, language)
    
    # 组装完整提示词
    prompt = f"""你是一位才华横溢的小说家。请根据以下角色设定和玩家状态，写一段生动的故事。
{story_context}{summary_context}{inner_drive_context}{narrative_context}{emotion_guidance}{style_context}{theme_context}

【角色设定】
{character_context}
...
"""
```

### 8.3 事件后更新流程

```python
# src/game/story_depth_manager.py

class StoryDepthManager:
    """故事深度管理器：协调各模块的更新"""
    
    def __init__(self, ai_client: AIClient):
        self.inner_drive_updater = InnerDriveUpdater(ai_client)
        self.narrative_planner = NarrativePlanner(ai_client)
        self.emotion_analyzer = EmotionAnalyzer(ai_client)
        self.theme_evolver = ThemeEvolver(ai_client)
    
    def initialize(self, player_state: PlayerState, language: str = "zh") -> None:
        """初始化所有深度系统"""
        # 1. 初始化内驱力
        ids = self.inner_drive_updater.initialize_from_character_settings(
            player_state.character_settings, language
        )
        player_state.inner_drive_state = ids.to_dict()
        
        # 2. 规划叙事弧线
        arc = self.narrative_planner.plan_arc(
            player_state.life_vision,
            player_state.character_settings,
            settings.TOTAL_WEEKS,
            language
        )
        player_state.narrative_arc = arc.to_dict()
        
        # 3. 初始化主题
        tracker = self.theme_evolver.initialize_themes(
            player_state.life_vision, ids, language
        )
        player_state.theme_tracker = tracker.to_dict()
        
        # 4. 初始化情感曲线
        player_state.emotion_curve = EmotionCurve().to_dict()
    
    def update_after_event(
        self,
        player_state: PlayerState,
        event_description: str,
        player_choice: str,
        outcome: str,
        language: str = "zh"
    ) -> None:
        """事件后更新所有深度系统"""
        week = player_state.week
        
        # 1. 更新内驱力
        # 2. 更新情感曲线
        # 3. 检查关键事件完成
        # 4. 更新主题探索
```

---

## 九、实施路线图

| 阶段 | 模块 | 主要任务 | 预计工作量 | 依赖 |
|------|------|----------|------------|------|
| **Phase 1** | 内驱力与成长弧线 | 数据结构 + 更新器 + 提示词集成 | 3-4天 | 无 |
| **Phase 2** | 叙事弧线规划 | 模板系统 + 规划器 + 关键事件检测 | 2-3天 | Phase 1 |
| **Phase 3** | 情感曲线追踪 | 分析器 + 节奏调整逻辑 | 1-2天 | Phase 2 |
| **Phase 4** | 风格配置 | 预定义模板 + 注入器 | 1天 | 无 |
| **Phase 5** | 主题追踪 | 初始化 + 演化器 + 高潮触发 | 2天 | Phase 1 |
| **Phase 6** | 集成测试 | 端到端测试 + 调优 | 2-3天 | All |

### 9.1 文件结构

```
src/game/
├── inner_drive/
│   ├── __init__.py
│   ├── models.py          # 数据结构
│   └── updater.py         # 更新器
├── narrative/
│   ├── __init__.py
│   ├── arc_models.py      # 数据结构
│   └── planner.py         # 规划器
├── emotion/
│   ├── __init__.py
│   ├── models.py          # 数据结构
│   └── analyzer.py        # 分析器
├── style/
│   ├── __init__.py
│   ├── models.py          # 数据结构
│   └── injector.py        # 注入器
├── theme/
│   ├── __init__.py
│   ├── models.py          # 数据结构
│   └── evolver.py         # 演化器
└── story_depth_manager.py # 协调器

config/prompts/
├── inner_drive_prompts.py  # 内驱力提示词
├── narrative_prompts.py    # 叙事弧线提示词
├── emotion_prompts.py      # 情感分析提示词
├── style_prompts.py        # 风格提示词
└── theme_prompts.py        # 主题提示词
```

---

## 十、待讨论事项

### 10.1 设计决策

| 问题 | 选项 | 建议 | 您的意见 |
|------|------|------|----------|
| 内驱力初始化时机 | A. 角色创建时自动<br>B. 玩家手动选择<br>C. 混合 | **C**：核心动机自动，玩家可微调 | |
| 叙事弧线可见性 | A. 完全隐藏<br>B. 玩家可查看<br>C. 作为游戏元素展示 | **B**：作为"人生轨迹"可视化 | |
| 风格配置方式 | A. 预设模板<br>B. 玩家自定义<br>C. AI分析玩家偏好 | **A+B**：提供模板，允许高级自定义 | |
| 主题选择 | A. AI自动选择<br>B. 玩家选择<br>C. 基于人生愿景推荐 | **C**：推荐+玩家确认 | |

### 10.2 技术问题

| 问题 | 说明 | 您的意见 |
|------|------|----------|
| AI调用次数增加 | 每周事件后需额外调用AI更新各模块状态，可能增加延迟 | |
| 状态持久化 | 新增字段需要数据库迁移 | |
| 向后兼容 | 旧存档如何处理新增字段 | |

### 10.3 优先级确认

请确认是否按照建议的顺序实施，或调整优先级：

1. ☐ 内驱力与成长弧线（核心）
2. ☐ 叙事弧线规划
3. ☐ 情感曲线追踪
4. ☐ 风格配置
5. ☐ 主题追踪

---

## 附录

### A. 参考资源

- 《故事》罗伯特·麦基
- 《作家之旅》克里斯托弗·沃格勒
- 《千面英雄》约瑟夫·坎贝尔
- 《情感曲线与叙事节奏》相关论文

### B. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-02-26 | 初始版本 |

---

> **下一步**: 请评审本方案，确认后即可开始实施 Phase 1。
