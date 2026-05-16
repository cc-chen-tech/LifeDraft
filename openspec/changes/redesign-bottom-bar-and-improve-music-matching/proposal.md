## Why

The current bottom area has three overlapping UI surfaces competing for the same space:

```
┌──────────────────────────────────┐
│       Game Screen                │
│     (story content)              │
├──────────────────────────────────┤  ← GlobalMusicPlayer (bottom-0)
│  🎵 ♫ 浮世绘 · 周杰伦          │
├──────────────────────────────────┤  ← ChatBar (bottom-14 / bottom-12)
│  [改写] [💬] ← 收起态            │
│  [重新生成][改写][总结] ← 展开态 │
└──────────────────────────────────┘
```

Three problems:
1. MusicPlayer 和 ChatBar 垂直堆叠在屏幕底部，挤压故事内容空间，移动端尤其严重
2. "改写"按钮重复三次：ChatBar 收起态一个、ChatBar 展开态一个、StoryAdjuster 里面还有一个"改写故事"按钮
3. StoryAdjuster 是独立 Sheet 组件，但功能和 ChatBar 的"改写"完全重叠

另外，音乐推荐匹配质量有提升空间：故事分析 prompt 需要更深的情绪/场景理解，搜索结果需要评分排序。

## What Changes

### UI 布局重设计

- **ChatBar 收起态**：只保留 💬 圆形按钮（去掉独立的"改写"按钮），右下角悬浮
- **ChatBar 展开态**：保留 重新生成/改写/总结 三个快捷操作 + 聊天输入框，从底部滑出
- **StoryAdjuster 删除**：其"改写故事"和"重新生成"功能完全由 ChatBar 承载。"改写"按钮打开改写 Sheet（原 StoryAdjuster 的核心逻辑内联到 ChatBar）
- **GlobalMusicPlayer 上移**：从 `bottom-0` 移到顶部 `top-0` 成为悬浮迷你播放条，展开时下拉完整播放器。不再和 ChatBar 堆叠

### 音乐匹配改进

- 用**完整 story_text** 做 AI 分析，不截断
- 增强分析 prompt：提取时代背景、情绪基调、场景类型、节奏感、能量级、乐器偏好
- 搜索结果加入**相关性评分和排序**
- AI 生成曲目仅插入后续队列，不切当前播放

## Capabilities

### New Capabilities

- `ui-bottom-layout`: ChatBar 精简、StoryAdjuster 删除、MusicPlayer 顶部悬浮、底部无重叠的布局系统

### Modified Capabilities

- `story-music-recommendation`: 增强故事分析 prompt、搜索结果 rerank、完整文本分析（已在 `improve-story-music-recommendation-and-premium-ai-queue` 中部分推进）

## Impact

- **删除** `frontend/src/components/game/StoryAdjuster.tsx`
- **重写** `frontend/src/components/game/ChatBar.tsx`：内联改写 Sheet、移除收起态"改写"按钮
- **重写** `frontend/src/components/game/GlobalMusicPlayer.tsx`：从 `bottom-0` 移到 `top-0`
- **修改** `frontend/src/app/play/page.tsx`：移除 StoryAdjuster 引用和状态，调整 ChatBar props
- **修改** `src/services/music_service.py`：增强 `_analyze_story_mood()`、添加 rerank 逻辑
- **新增测试**：ChatBar UI 契约测试、MusicPlayer 位置回归测试、音乐匹配质量契约测试
