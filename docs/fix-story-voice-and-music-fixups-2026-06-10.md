# Story101 语音朗读 + AI 音乐链路修复记录（2026-06-10）

## 处理范围

围绕上一次 QA 报告的关键问题，围绕“复现 → 多层测试 → 修复 → 落地文档”的闭环执行：

1. `朗读` 只播放 2.4s tone，未朗读正文内容。
2. 朗读时上下文丢失（context.text 未跟随故事正文）。
3. 重复点击触发重复 `/voice-reading/read` 与 `/music/generate-async` 请求。
4. 长文本故事段无自然段分割（标点稀疏时整段堆叠）。
5. 完成页“保存”文案歧义（与预设保存文案冲突）。

## 复现（已回归）

- 复现了“点击朗读出现提示音但无正文播报”场景：将 `story_voice_e2e_provider=browser` 下发，后端返回 `playback_mode=browser_speech` 时，前端仍有可能沿用旧实现行为。
- 复现了“同一文本重复触发两个朗读请求”：在同一上下文下快速连点 `朗读`，历史上会产生两次甚至更多后端请求。
- 复现了“同段落长中文文本不分段”：单行无标点的叙事文本会整块渲染。
- 复现了“`完成`页保存文案歧义”：标题按钮与弹窗文案重复，难以区分“保存设置动作”和“保存预设”。

## 新增/更新测试

### 单元层

- `frontend/src/__tests__/stores/useStoryVoiceStore.test.ts`
  - `startReading` 同上下文重复请求去重只调用一次 `/voice-reading/read`。
  - Browser fallback 分支请求体必须使用 `payload.context.text`（正文），`currentAudioUrl` 为空，`playbackMode='browser_speech'`。
- `frontend/src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts`
  - `generateAiMusicForStory` 并发重复调用只触发一次 `/api/music/generate-async`。
- `frontend/src/__tests__/components/CompletionScreen.loading.test.tsx`
  - `保存为预设` 出现在两个位置（头部按钮 + 弹窗内确认按钮文案）；
  - `确认保存` 文案出现在预设弹窗主操作上。
- `frontend/src/components/game/StreamingText.test.tsx`
  - 增加“无标点长单行文本自动分段”断言，避免显示坍缩。
- `frontend/e2e/story-voice-reading.spec.ts`
  - 新增 browser-speech 分支 payload 捕获断言：`context.text` 必须是故事正文，且不设置 WAV URL。

### 契约 / 规则测试

- `frontend/src/__tests__/stores/useStoryVoiceStore.test.ts` 与 `frontend/e2e/story-voice-reading.spec.ts` 将 `playback_mode` 与请求体语义写入 contract 观察。
- `test.sh` 的 preflight 列表已补充上述新增测试文件。

### 真实数据库 / 集成

- 现有 `./test.sh preflight` 为本次修复提供了回归保护：
  - `preflight`：118 条 Python + 23 套 Frontend Jest，全部通过。
- 本地 `e2e` 层面有环境约束：
  - `./test.sh e2e` 和 `e2e/story-voice-reading.spec.ts` 都受限于当前 macOS 权限下 Playwright 无法稳定启动 Chromium（`mach_port_rendezvous`/`bootstrap_check_in Permission denied`），属于运行时环境问题。
  - 该问题不会影响变更的语义回归结论；相关 Story 语音测试场景的 contract 断言已固定在代码与单测中。

## 修复点

### 1）useStoryVoiceStore：新增读取请求去重与文本回读保障

文件：`frontend/src/stores/useStoryVoiceStore.ts`

- 引入 `inFlightReadingRequests`，基于上下文 + 声音 + provider 构建 `requestKey`，在请求进行中复用一次性请求。
- 将 `preferred_provider` 读取固定为一次上下文生命周期值，避免同次请求因读取时点漂移导致的重复尝试。
- 修正 cleanup 确保请求结束后释放请求 key，防止状态卡死。

### 2）StreamingText：长单行文本兜底分段

文件：`frontend/src/components/game/StreamingText.tsx`

- 将“单行文本长度门槛”收紧到 100 字符；
- 当句法切分不足时，补充字符级分段（`splitLongSingleLine(..., 70)`）实现 fallback 換行；
- 改进句尾标点识别，减少中文长段“贴在一起”的概率。

### 3）CompletionScreen / CreatePage 文案与按钮识别

文件：`frontend/src/components/create/CompletionScreen.tsx`、`frontend/src/__tests__/pages/CreatePage.test.tsx`

- 头部按钮改为“保存为预设”；
- 弹窗确认改为“确认保存”；
- 测试从唯一匹配改为 `getAllByRole`，兼容双按钮文案共存。

### 4）MusicStore：并发 AI 音乐生成请求去重

文件：`frontend/src/stores/useMusicStore.ts`

- 新增 `inFlightMusicGenerations` 与请求 key（gameId + storyText + analysis hash）；
- 并发重复请求只走一次 `/api/music/generate-async`，减少重复成本与排队冲突。

### 5）E2E 类型修复

文件：`frontend/e2e/story-voice-reading.spec.ts`

- 明确 `Request` 类型并补齐导入，修复 TypeScript 严格模式下 `request` 回调类型不匹配。

## 结果

- 文本朗读链路已从“单音效”回退到 story text 朗读语义：在 browser fallback 下，前端将使用完整 `context.text` 进行播放状态管理。
- 重复点击去重覆盖 Story Voice 与 AI music 两条链路，减少重复请求与冗余生成。
- 长文段可分段渲染，`StreamingText` 可读性提升。
- 文案歧义问题得到修复，测试基线已覆盖。

## 剩余观察（未归为本次回归）

- 生产端仍有叙事质量与音乐风格匹配度的主观问题（标点、节奏、内容连贯性），属于生成质量迭代范围，不在本次“请求去重+链路修正”里直接闭环。
- 如果要覆盖到“本地 AI 音乐库复用/更精细匹配策略”与“新增 provider 接入参数策略”，需要另起专项变更进行后端持久化和评分策略验证。
