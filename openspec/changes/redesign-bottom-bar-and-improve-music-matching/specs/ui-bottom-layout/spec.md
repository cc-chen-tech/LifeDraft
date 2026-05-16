## ADDED Requirements

### Requirement: ChatBar collapsed shows only a chat bubble
ChatBar 收起时 MUST 仅显示一个圆形 💬 按钮，MUST NOT 显示独立的"改写"按钮。

#### Scenario: Collapsed state
- **WHEN** ChatBar 处于收起态且 gameId 有效
- **THEN** 在右下角显示一个圆形 MessageCircle 按钮
- **AND** 不渲染任何独立的"改写"按钮

### Requirement: ChatBar expanded includes rewrite as inline sheet
ChatBar 展开后的"改写"按钮 MUST 触发一个内联改写 Sheet，不再通过外部回调打开 StoryAdjuster。

#### Scenario: Rewrite button opens inline sheet
- **WHEN** 用户点击 ChatBar 展开态的"改写"按钮
- **THEN** 打开一个底部 Sheet，包含改写指令输入框和"改写故事"按钮
- **AND** Sheet 的行为和原 StoryAdjuster 一致（SSE 流式改写、完成关闭）

#### Scenario: Rewrite sheet receives story text
- **WHEN** 改写 Sheet 打开
- **THEN** 输入框 placeholder 提示用户描述修改
- **AND** 改写请求使用当前 fullStory 作为上下文

### Requirement: StoryAdjuster component is deleted
`StoryAdjuster.tsx` 组件 MUST 被删除，其功能完全由 ChatBar 承接。

#### Scenario: StoryAdjuster no longer exists
- **WHEN** 代码库搜索 StoryAdjuster 引用
- **THEN** play/page.tsx 不再 import StoryAdjuster
- **AND** StoryAdjuster.tsx 文件被删除
- **AND** 没有残留的 `showAdjuster` / `setShowAdjuster` 状态

### Requirement: MusicPlayer positioned at top
GlobalMusicPlayer MUST 从 `bottom-0` 移到 `top-0`，MUST NOT 和 ChatBar 在底部区域重叠。

#### Scenario: Mini player at top
- **WHEN** 游戏页面加载且音乐已加载
- **THEN** GlobalMusicPlayer 迷你条固定在屏幕顶部
- **AND** 迷你条不与 StatusBar 或 RoundSceneImage 重叠

#### Scenario: Expanded player drops down
- **WHEN** 用户点击顶部迷你条展开
- **THEN** 完整 MusicPlayer 从顶部向下展开
- **AND** Chevron 图标方向从 ▲ 变为 ▼

### Requirement: No bottom-area overlap
在移动端视口（<768px），底部 MUST 仅显示 ChatBar（展开或收起），没有音乐播放器条。

#### Scenario: Mobile viewport bottom area
- **WHEN** 视口宽度 < 768px
- **THEN** 视口底部只有 ChatBar 组件
- **AND** 音乐播放器迷你条在顶部
