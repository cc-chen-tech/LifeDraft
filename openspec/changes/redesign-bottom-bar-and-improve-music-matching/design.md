## Context

当前底部交互区有三个组件竞争同一块屏幕空间：

```
当前布局（移动端视口 ≈ 800px 高）:

┌─────────────────────────────────────┐ ┬
│    StatusBar         42px           │ │
│    RoundSceneImage   ~200px         │ │
│                                     │ │
│    Story Text (scrollable)          │ │ ~350px 留给故事
│                                     │ │
│    OptionCards        ~120px        │ │
├─────────────────────────────────────┤ ┤
│ 🎵 GlobalMusicPlayer  52px         │ │ bottom-0, full-width
│    ♫ 浮世绘 · 周杰伦  ──────────  │ │
├─────────────────────────────────────┤ ┤
│ [改写] [💬]  收起态    48px        │ │ bottom-14
│                                     │ │
│ 展开态:                            │ │
│ [重新生成][改写][总结][清空][✕]    │ │
│ [chat messages max-h-200px]        │ │ bottom-12, 可占 250px+
│ [_________输入框_________][发送]   │ │
└─────────────────────────────────────┘ ┴

问题:
- 音乐条 + ChatBar 共同占据 100-300+px 底部空间
- 移动端故事可视区被压缩到 ~350px
- "改写"按钮在 3 个地方重复出现
- StoryAdjuster Sheet 独立维护一套参数/回调链
```

## Goals / Non-Goals

**Goals:**
- ChatBar 收起时只显示一个 💬 按钮，不占横向空间
- "改写"功能只有一个入口：ChatBar 展开后的"改写"按钮
- 音乐播放器从底部移到顶部，和 ChatBar 从空间上分离
- 音乐分析使用完整故事文本，不截断
- Netease 搜索结果按相关性评分排序

**Non-Goals:**
- 不改变 MusicPlayer 内部逻辑和音频播放行为
- 不改变 SSE 流式改写/重新生成的后端接口
- 不在这次变更中完成 AI 音乐生成 provider 的具体实现

## Proposed Layout

```
新布局:

┌─────────────────────────────────────┐ ┬
│ 🎵 ♫ 浮世绘 · 周杰伦  ═══════ ▲  │ │ top-0, 半透明悬浮迷你条
├─────────────────────────────────────┤ ┤ 点击展开完整播放器下拉
│    StatusBar                        │ │
│    RoundSceneImage                  │ │
│                                     │ │
│    Story Text (scrollable)          │ │ ~450px 留给故事 (+100px)
│                                     │ │
│    OptionCards                      │ │
│                                     │ │
│                              [💬]   │ │ 右下角悬浮圆形按钮
├─────────────────────────────────────┤ ┤
│ [重新生成][改写][总结][清空][✕]    │ │ 展开态从底部滑出
│ [chat messages...]                 │ │
│ [_________输入框_________][发送]   │ │
└─────────────────────────────────────┘ ┴

关键变化:
- MusicPlayer: bottom → top, 迷你条常驻, 点击下拉展开
- ChatBar 收起: 只一个圆形 💬 按钮在右下
- ChatBar 展开: "改写"按钮直接在当前组件内打开改写 Sheet
- StoryAdjuster.tsx: 删除, 其 Sheet+逻辑内联到 ChatBar
```

## Architecture Decision: Inline StoryAdjuster into ChatBar

ChatBar 已有的 `onAdjustStory` prop 只是在 play/page.tsx 设置 `setShowAdjuster(true)`。改为 ChatBar 内部直接管理改写 Sheet 状态。

```
Before:
  ChatBar → onAdjustStory() → play/page setShowAdjuster(true) → StoryAdjuster Sheet

After:
  ChatBar → 内部 useState → 改写 Sheet (内联, 复用 ChatBar 的 gameId/storyText)
```

ChatBar 需要的新 inputs:
- `storyText: string` — 当前故事全文（用于改写的 fullStory 参数）
- `onRewriteComplete: (newStory: string) => void` — 改写完成回调

删除的 props:
- `onAdjustStory?: () => void` — 不再需要外部回调

## Architecture Decision: MusicPlayer Top Position

```css
/* Before */
.fixed.z-50.bottom-0.left-0.right-0

/* After */  
.fixed.z-50.top-0.left-0.right-0
```

展开行为从 "向上弹出" 变为 "向下展开"。迷你条的 Chevron 方向反转。

桌面端保持原有的 `md:bottom-4 md:left-auto md:right-4 md:w-80` 行为不变（桌面侧边悬浮）。

## Music Matching: Full Story Analysis

当前 `_analyze_story_mood()` 截取了 `story_text[:800]`。改为使用完整文本：

```python
# Before
return self._call_ai_for_analysis(story_text[:800])

# After  — AI 模型 token 限制由 client 层处理, 不在 service 层截断
return self._call_ai_for_analysis(story_text)
```

搜索词构建从单一 mood 词扩展为多维度组合：

```python
query_parts = []
if brief.mood: query_parts.append(brief.mood)
if brief.era_or_environment: query_parts.append(brief.era_or_environment)  
if brief.scene_type: query_parts.append(brief.scene_type)
if brief.instruments: query_parts.extend(brief.instruments[:2])
```

搜索结果按 brief 匹配度排序（简单 TF-IDF 风格的相关性分）。

## Risks / Trade-offs

- **MusicPlayer 在顶部**可能在移动端和 StatusBar 重叠 → 给 `top` 加 margin 避开 status bar
- **ChatBar 内联改写**增加组件复杂度 → 抽 `RewriteSheet` 子组件保持可读性
- **完整文本分析**增加 AI token 消耗 → 对很长的故事（>50 周）可保留一个较高的上限（如 8000 字），但不再用 800 字的过低值
