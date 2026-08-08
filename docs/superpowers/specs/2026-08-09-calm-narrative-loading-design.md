# Story Life 统一叙事加载体验设计

> 状态：设计已批准，进入实现  
> 日期：2026-08-09  
> 视觉方向：炭黑留白  
> 范围：所有 `SkeletonStory` 使用页面、`AutoGenScreen` 以及它们依赖的前端生成状态与恢复逻辑

## 1. 目标

Story Life 的长叙事等待应像翻到尚未写完的下一页：安静、可信、知道系统仍在工作，也知道异常时能做什么。当前界面把旋转图标、重复文案、质量档位、实时秒数、预估区间、骨架条和底部禁用按钮叠在一起，既制造视觉噪音，也混淆真实阶段与时间推测。

本次统一为一套叙事加载语言：正常等待只显示一个标题、一个真实阶段和一条低对比分隔线；收到正文后立刻退到文末紧凑状态；只有连接异常或失败时才显示操作。

## 2. 范围边界

- 统一 hydration、角色单步、角色自动生成、开场、游戏事件/选择、结局六类叙事等待。
- 重构前端状态、流式切换、轮询隔离、无活动 watchdog 与错误恢复。
- 不修改后端 API、数据库、持久化模型或生成任务模型。
- 不改变图片、音乐、头像和按钮内部的小型加载器。
- 不改变应用全局主题；视觉 token 只属于叙事加载组件。
- 单一前端 PR，无 feature flag、无迁移；整体 revert 即可回滚。

## 3. 统一接口

```ts
type NarrativeLoadingContext =
  | "hydrate"
  | "character-step"
  | "character-auto"
  | "opening"
  | "gameplay"
  | "ending";

type NarrativeLoadingLayout = "screen" | "section" | "inline";
type NarrativeLoadingOperation = "event" | "choice";
type NarrativeTransportState =
  | "active"
  | "reconnecting"
  | "polling"
  | "failed";
```

`NarrativeLoadingState` 接收 `context`、`layout`、原始 `phase`，以及可选的 `operation`、`stepLabel`、`contextLabel`、`delayed`、`transport` 和 `onAction`。组件只负责展示；文案由纯函数 `resolveNarrativeLoadingCopy()` 解析；延迟由一次性 timeout 的 `useDelayedLoading()` 提供。

所有实例只产生一个 `aria-live`/`role=status` 区域。按钮不进入 live region，避免状态变化重复播报。

## 4. 状态与文案

| 场景 | 主标题 | 正常状态来源 | 延迟阈值 |
|---|---|---|---|
| Hydration | 正在打开这一页 | 无 | 250ms 后才显现 |
| 单步角色设定 | 角色设定，正在成形 | 当前真实步骤 | 15 秒 |
| 自动角色背景 | 角色背景，正在补全 | 当前实际生成步骤 | 30 秒 |
| 开场故事 | 人生开篇，正在落笔 | 首段前固定；首段后文末状态 | 当前质量档位上限 |
| 游戏事件/选择 | 下一页，正在展开 | 真实 SSE phase | fast 45s / expert 90s / master 180s |
| 结局 | 这一生，正在收束 | 获取/整理结局状态 | 15 秒 |

后端原始阶段归并为五组：

- 准备：`preparing`、`resuming`、`initializing`
- 梳理：`loading_context`、`building_world`
- 写作：`generating`、`generating_story`、`retry`、`retrying`
- 校对：`validating`
- 准备选择：`generating_options`

`completed` 由页面切换到可操作态，不作为加载文案；`failed` 进入失败 transport。未知阶段在事件/开场等写作语境回退为“正在继续写作”，在选择结果语境回退为“正在继续推演”。

正常和单纯延迟的 `active` 状态不显示按钮。`reconnecting` 与 `polling` 显示“重新连接”，`failed` 显示“重试”。延迟提示不显示秒数、质量档位或预计区间，只用克制的文字说明仍在继续。

## 5. 视觉系统

加载态使用六个私有 token：

- `--narrative-ink: #11100F`
- `--narrative-depth: #0D0C0B`
- `--narrative-paper: #F0ECE6`
- `--narrative-muted: #8F8881`
- `--narrative-rule: #34302C`
- `--narrative-accent: #71675D`

标题使用中文宋体栈，正文/辅助信息沿用产品正文栈。界面以大面积炭黑留白、短行标题和细分隔线建立“章节间页”感。唯一动态元素是分隔线 2.8 秒的低幅度呼吸；`prefers-reduced-motion: reduce` 下完全静止。

明确禁止 spinner、pulse、skeleton、shimmer、渐变光晕、百分比、伪进度、质量档位、预计区间、实时秒数和“AI”字样。

## 6. 页面行为

### 6.1 Hydration 与角色生成

Hydration 在 250ms 内不渲染可见加载内容，避免快速路由恢复时闪屏。角色单步显示当前步骤。自动角色生成在循环开始和每次步骤切换时更新真实步骤，而不是停留在泛化的“正在生成”。

### 6.2 开场

收到首个 story chunk 前显示 `screen` 章节间页。首个 chunk 到达后，整页加载态立即卸载，正文开始显示，生成未结束时只在正文末尾显示 `inline` 状态。两者不能同屏。

### 6.3 游戏事件与选择

空正文时显示 `section` 加载态；已有部分正文时只显示文末 `inline` 状态。独立恢复卡与整页 reload 删除。连接中断由 transport 状态统一呈现。

生成期间 `ChatBar` 继续挂载以保留聊天历史，但组件不产生可见 DOM；进入 busy 时关闭展开面板、改写 Sheet 和总结 Sheet。恢复可操作后淡入返回。

### 6.4 结局

结局获取与整理使用统一加载态。请求失败进入显式失败状态并提供“重试”；重试重发结局请求，不刷新整页。空成功响应也按失败处理，避免永久等待或空白完成。

## 7. 流式与恢复安全

- 每次游戏生成建立唯一客户端 run ID 和 `AbortController`；回调、轮询和 watchdog 写状态前必须确认仍是当前 run。
- `AbortError` 表示有意中止旧连接，不启动 polling、不显示失败。
- SSE 可恢复错误先进入 `reconnecting`，需要同步查询时进入 `polling`；成功完成回到 `active` 并退出加载，确定失败进入 `failed`。
- 轮询同时绑定 run ID 和 abort signal；旧 run 被替换后立即退出，不得回写 story、options、phase 或 transport。
- 删除从 retry 状态开始计时的固定 60 秒 watchdog。改为无活动 watchdog：每次真实 SSE status、story、complete、error 活动都重置，只有连续无活动才触发恢复。

## 8. 可访问性与验收

- 每个加载实例只有一个 live region，文案变化不会因秒表重复播报。
- 异常操作使用真实 `<button>`，具有可见 focus 状态。
- 1440×900 与 390×844 均无横向溢出和布局跳变。
- 正常态没有任何时间文字；首个 chunk 后没有整页加载态。
- reduced-motion 媒体查询下动画名称为 `none`，不是极短动画。
- E2E fixture 可确定性切换初始、部分正文、延迟、重连、轮询和失败状态。

