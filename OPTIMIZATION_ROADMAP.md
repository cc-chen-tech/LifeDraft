# 后端代码质量优化路线图

## 优化计划概述

**总体评分**: 6.5/10  
**预计优化工作**: 4-8周  
**优先级**: Critical (1周) → High (2-3周) → Medium (2-4周)

---

## Phase 1: 基础清理 (第1-2周)

### Task 1.1: 修复异常处理 (Critical)
**优先级**: P0  
**文件数**: 49个  
**问题数**: 193处  
**工作量**: 中等

**具体任务**:
1. 定义自定义异常类
   ```python
   # 创建 src/exceptions.py
   class GameException(Exception):
       """Game系统基异常"""
       def __init__(self, message: str, context: Dict[str, Any] = None):
           super().__init__(message)
           self.context = context or {}
   
   class AIGenerationError(GameException):
       """AI生成失败"""
       pass
   
   class DataExtractionError(GameException):
       """数据提取失败"""
       pass
   ```

2. 逐个修复异常处理
   - `/src/database/db.py`: 2处 (line 397, 765)
   - `/src/game/world_model_updater.py`: 5处 (line 352, 406, 540, 576, 694)
   - `/src/game/story_service.py`: 5处 (line 89, 183, 243, 364, 442)
   - `/src/game/character_creation.py`: 4处 (line 371, 427, 732, 801)
   - 其他37个文件

3. 添加错误上下文
   ```python
   # Before
   except Exception as e:
       logger.error(f"Failed: {e}")
       return []
   
   # After
   except DataExtractionError as e:
       logger.error(
           f"Data extraction failed: {e}",
           extra={"context": e.context}
       )
       raise  # 或返回有意义的错误响应
   ```

**验收标准**:
- [ ] 创建了 src/exceptions.py
- [ ] 所有裸except已替换为特定异常
- [ ] 所有关键错误路径添加了上下文信息
- [ ] 添加了相应的单元测试

---

### Task 1.2: 修复循环依赖 (Critical)
**优先级**: P0  
**循环数**: 2处  
**工作量**: 小

**Cycle 1: api.deps ↔ api.services.session_service**
```
问题:
api/deps.py:18
  from src.api.session_store import GameLoopSession, session_store

api/services/session_service.py:18
  from src.api.deps import get_db

解决方案:
1. api/deps.py 改用延迟导入
2. 或者：将 session_store 提取到单独的模块，仅被导入

改进代码:
# api/deps.py
def get_db() -> GameDatabase:
    # 延迟导入，避免循环
    if not hasattr(get_db, '_instance'):
        get_db._instance = GameDatabase()
    return get_db._instance

# api/services/session_service.py
from src.api.session_store import GameLoopSession, session_store
# 不直接导入 get_db，而是在方法中导入
```

**Cycle 2: game.state ↔ game.player_service**
```
问题:
game/state/__init__.py
  imports CharacterState from game.state.character_state

game/state/character_state.py
  imports PlayerState from game.state

game/player_service.py
  imports PlayerState, CharacterState

解决方案:
使用TYPE_CHECKING进行延迟导入:

# game/state/character_state.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.state.player_state import PlayerState

# game/player_service.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.state import PlayerState
```

**验收标准**:
- [ ] 修复了2处循环依赖
- [ ] 运行 `python -c "import src"` 无错误
- [ ] 单元测试通过

---

## Phase 2: 结构优化 (第2-4周)

### Task 2.1: 分解超大函数 (High)
**优先级**: P1  
**函数数**: 3个  
**工作量**: 中等

#### 2.1.1 分解 game.round.event_generator.generate_round_event() (354行)

**当前结构** (line 76-430):
```python
def generate_round_event(self, stream_callback, status_callback, session):
    # 1. 检查缓存的事件
    # 2. 构建上下文
    # 3. 调用AI生成
    # 4. 处理超时
    # 5. 回退处理
```

**重构方案** - 分解为5个函数:
```python
def generate_round_event(self, ...):
    # 主流程
    if self._current_event and self._current_event.options:
        return self._current_event
    
    context = self._build_event_context()
    try:
        event = self._call_ai_with_timeout(context, stream_callback)
    except TimeoutError:
        event = self._handle_generation_timeout()
    
    self._current_event = event
    return event

def _build_event_context(self) -> Dict[str, Any]:
    # 构建上下文 (~50行)
    return {
        'player_state': ...,
        'world_model': ...,
        ...
    }

def _call_ai_with_timeout(self, context, stream_callback):
    # AI调用 (~100行)
    ...

def _handle_generation_timeout(self):
    # 超时处理 (~50行)
    ...
```

**验收标准**:
- [ ] 主函数 <100行
- [ ] 每个子函数职责单一
- [ ] 所有测试通过
- [ ] 文档更新

#### 2.1.2 分解 api.routers.collection.get_collection() (285行)

**当前问题**: 路由层混入过多业务逻辑

**重构方案**:
```python
# Before
@router.get("/{game_id}")
async def get_collection(game_id: int, user: User = Depends(...)):
    # 285行混乱的数据处理逻辑
    
# After
@router.get("/{game_id}")
async def get_collection(game_id: int, user: User = Depends(...)):
    collection = collection_service.get_collection(game_id, user)
    return collection

# 创建 src/api/services/collection_service.py
class CollectionService:
    def get_collection(self, game_id: int, user: User) -> CollectionResponse:
        # 提取所有业务逻辑
        characters = self._build_character_collection(game_id)
        items = self._build_item_collection(game_id)
        landmarks = self._build_landmark_collection(game_id)
        return CollectionResponse(characters, items, landmarks)
```

**验收标准**:
- [ ] 路由函数 <50行
- [ ] 所有业务逻辑在Service层
- [ ] 测试更容易编写

#### 2.1.3 分解 services.image.scene_service.generate_round_scene_image() (267行)

**重构**: 分为生成、处理、保存三个方法

---

### Task 2.2: 提取路由业务逻辑 (High)
**优先级**: P1  
**文件数**: 5个  
**工作量**: 中等

**主要路由**:
1. `/src/api/routers/collection.py:47` (get_collection, 285行)
2. `/src/api/routers/images.py:94` (generate_image, 123行)
3. `/src/api/routers/images.py:221` (batch_generate_character_images, 179行)

**建立标准的服务层架构**:
```
api/routers/ (路由层, <50行/函数)
  ↓ calls
api/services/ (业务逻辑层)
  ↓ calls
src/game/ or src/services/ (领域逻辑)
  ↓ calls
src/database/ (数据访问)
```

---

### Task 2.3: 减少参数爆炸 (High)
**优先级**: P1  
**函数数**: 3个  
**工作量**: 中等

#### 2.3.1 重构 ai.story_generator.generate_round_event() (21参数)

**当前**:
```python
def generate_round_event(
    self, player_state, world_model, current_round,
    summary_selector, character_introduction_service,
    narrative_manager, relationship_service, ai_generator,
    ... # 13个参数
):
```

**改进** - 使用Context对象:
```python
class EventGenerationContext:
    player_state: PlayerState
    world_model: WorldModel
    current_round: int
    # ... 其他字段

def generate_round_event(self, context: EventGenerationContext):
    # 使用 context.player_state 等
```

**验收标准**:
- [ ] 创建了EventGenerationContext
- [ ] generate_round_event()参数 <5个
- [ ] 所有调用点更新

---

## Phase 3: 架构重构 (第4-8周)

### Task 3.1: 拆分超大类 (High)
**优先级**: P2  
**工作量**: 大

#### 3.1.1 拆分 ImageClient (1658行)

**当前结构**:
```python
class ImageClient:
    # 文生图 - 10个方法
    # 图生图 - 8个方法
    # 工具函数 - 12个方法
    # 模型降级 - 5个方法
```

**拆分方案**:
```python
# 1. 基础客户端
class ImageClientBase:
    """通用HTTP请求、重试、超时处理"""
    
# 2. 文生图客户端
class TextToImageClient(ImageClientBase):
    """文本生成图像"""
    
# 3. 图编辑客户端
class ImageEditClient(ImageClientBase):
    """图像编辑、修复"""
    
# 4. 工厂
class ImageClientFactory:
    @staticmethod
    def create(model_type: str) -> ImageClientBase:
        ...
```

#### 3.1.2 拆分 GameDatabase (929行)

**按功能拆分**:
```python
class GameRepository:
    """游戏管理"""
    def create_game(self): ...
    def get_game(self): ...
    
class GameStateRepository:
    """游戏状态"""
    def save_state(self): ...
    def load_state(self): ...
    
class DecisionRepository:
    """决策记录"""
    def save_decision(self): ...
```

#### 3.1.3 拆分 PlayerState (862行)

**分离数据和逻辑**:
```python
# 数据模型 (Pydantic)
class PlayerStateData(BaseModel):
    player_name: str
    energy: int
    mood: int
    # ... 字段

# 业务逻辑
class PlayerStateManager:
    def __init__(self, state: PlayerStateData):
        self.state = state
    
    def initialize_from_settings(self, settings): ...
    def update_energy(self, delta): ...
```

---

### Task 3.2: 统一AI调用模式 (Medium)
**优先级**: P2  
**工作量**: 小

**创建 BaseExtractionService**:
```python
# src/services/base_extraction_service.py

class BaseExtractionService:
    """提取服务基类，消除重复代码"""
    
    def __init__(self, ai_client, language: str = "zh"):
        self.ai_client = ai_client
        self.language = language
    
    def call_ai_and_parse(
        self,
        sys_prompt_key: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Optional[Dict]:
        """统一的AI调用和JSON解析"""
        sys_prompt = get_system_prompt(sys_prompt_key, self.language)
        response = self.ai_client.call(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return extract_json(response)

# 使用
class ItemExtractionService(BaseExtractionService):
    def extract_items(self, story_text: str) -> List[ItemState]:
        data = self.call_ai_and_parse(
            sys_prompt_key="story_analyzer",
            user_prompt=build_item_prompt(story_text),
        )
        return self._parse_items(data)
```

---

### Task 3.3: 改进错误处理 (Medium)
**优先级**: P2  
**工作量**: 中等

**步骤**:
1. 定义错误层级
2. 添加上下文信息
3. 统一错误恢复策略

**示例**:
```python
# 定义错误层级
class GameException(Exception):
    """基异常"""
    pass

class AIException(GameException):
    """AI相关错误"""
    pass

class DataException(GameException):
    """数据处理错误"""
    pass

class ValidationException(GameException):
    """验证错误"""
    pass

# 使用
try:
    data = extract_json(response)
except json.JSONDecodeError as e:
    raise DataException(
        "JSON parsing failed",
        context={
            "game_id": game_id,
            "response_len": len(response),
            "response_preview": response[:200]
        }
    ) from e
```

---

### Task 3.4: 统一提示词管理 (Medium)
**优先级**: P2  
**工作量**: 中等

**目标**: 移除所有硬编码提示词

**当前问题**:
- `/src/ai/image_client.py:136-147` 硬编码system prompt
- 多个AI生成器中的inline提示词

**统一方案**:
```python
# config/prompts/__init__.py

class PromptRegistry:
    """中央提示词注册表"""
    
    PROMPTS = {
        "image.text_to_image": PromptTemplate(...),
        "story.generation": PromptTemplate(...),
        "entity.recognition": PromptTemplate(...),
    }
    
    @classmethod
    def get_prompt(cls, key: str, **kwargs) -> str:
        template = cls.PROMPTS[key]
        return template.format(**kwargs)
    
    @classmethod
    def get_system_prompt(cls, key: str, language: str) -> str:
        # 返回系统提示词
        ...
```

---

## 检查清单

### Phase 1 (第1-2周)
- [ ] Task 1.1: 异常处理修复完成
  - [ ] 创建 src/exceptions.py
  - [ ] 49个文件已修复
  - [ ] 单元测试通过

- [ ] Task 1.2: 循环依赖修复完成
  - [ ] api.deps 循环已修复
  - [ ] game.state 循环已修复
  - [ ] 导入测试通过

### Phase 2 (第2-4周)
- [ ] Task 2.1: 超大函数分解完成
  - [ ] generate_round_event() <100行
  - [ ] get_collection() <50行
  - [ ] generate_round_scene_image() 分解完成

- [ ] Task 2.2: 路由业务逻辑提取完成
  - [ ] 创建 api/services/ 下的服务类
  - [ ] 路由函数简化

- [ ] Task 2.3: 参数爆炸减少
  - [ ] EventGenerationContext 创建
  - [ ] 关键函数参数 <5个

### Phase 3 (第4-8周)
- [ ] Task 3.1: 超大类拆分完成
  - [ ] ImageClient 拆分为3个类
  - [ ] GameDatabase 拆分为3个repository
  - [ ] PlayerState 分离为数据+逻辑

- [ ] Task 3.2: AI调用模式统一
  - [ ] BaseExtractionService 创建
  - [ ] 重复代码消除 >80%

- [ ] Task 3.3: 错误处理改进
  - [ ] 异常层级完善
  - [ ] 所有关键路径有上下文

- [ ] Task 3.4: 提示词管理统一
  - [ ] PromptRegistry 创建
  - [ ] 硬编码提示词移除 >90%

---

## 预期改进

**完成后的质量评分**: 8.5/10 (从6.5/10)

| 指标 | 前 | 后 | 改进 |
|-----|----|----|------|
| 异常处理 | 4/10 | 9/10 | +5 |
| 代码复杂度 | 5/10 | 7/10 | +2 |
| 模块职责 | 6/10 | 8/10 | +2 |
| 可维护性 | 6/10 | 8/10 | +2 |
| 代码重复 | 5/10 | 8/10 | +3 |
| 平均分 | 5.2 | 8.0 | +2.8 |

**额外好处**:
- 测试编写更容易 (+30%生产力)
- 新功能开发更快 (+25%)
- Bug修复时间减少 (-30%)
- 代码审查时间减少 (-40%)

