# Story101.live 深度体验复测报告

测试时间：2026-06-08 15:08-16:38（Asia/Shanghai）
测试环境：生产 `https://story101.live`
部署提交：`3385ed2839ab80cbdd8ec4fc183ea2a8f4e629e8` + PR 分支补丁 `1fdfa4ac`
测试账号：本轮新注册账号（密钥截图仅作本地证据，不在报告中展开）
测试游戏：`game_id=95`，顾晨曦，2020年代中国互联网 / AI协作工具 / 产品经理成长线；已从创建流程推进到第 4 周。

## 结论

本轮生产已经包含 PR #51 代码，MiniMax 环境变量生效，TTS 和音乐生成的核心后端链路都能跑通。

初次长流程在第 2 周入口复现空白主内容阻断。该问题已在本轮补回归测试并修复为：继续周总结/下一轮后强制触发事件生成，避免 stale phase/generating 状态挡住 `/event`。补丁热部署后，刷新同一个 `game_id=95` 能恢复第 2 周事件生成，并继续推进到第 4 周。

## 部署与 CI 状态

- 生产 ECS `/opt/story2` 已部署到 `3385ed2839ab80cbdd8ec4fc183ea2a8f4e629e8`，并热打 PR 分支补丁 `1fdfa4ac` 的前端状态机修复。
- 生产健康检查通过：`/api/health` 和 `/health` 正常。
- GitHub PR #51 checks 仍红，但 GitHub run/job 没有 runner/steps，`gh run view --log` 返回 `log not found`。这不是本地测试失败形态，仍属于 CI/runner 层面的发布不稳定因素。
- 生产 MiniMax 配置已生效：`MINIMAX_API_KEY` 可用，`STORY_TTS_PROVIDER=minimax`，`backend_audio_enabled=true`。

## 已验证通过

### MiniMax TTS

- `/api/voice-reading/settings` 返回：
  - `tts_provider=minimax`
  - `backend_audio_enabled=true`
  - `playback_mode=audio`
  - 声音：`warm_female` / `calm_male` / `clear_neutral`
- 手动朗读三种声音均生成真实后端音频：
  - `warm_female-minimax-speech-02-turbo.mp3`
  - `calm_male-minimax-speech-02-turbo.mp3`
  - `clear_neutral-minimax-speech-02-turbo.mp3`
- 自动朗读开启后，会在故事和选项稳定后触发新的 `/api/voice-reading/read`。

问题：自动朗读触发延迟较长，UI 没有“正在准备自动朗读”的状态；播放中仍显示“朗读当前故事”，状态表达混乱。

### MiniMax 音乐生成

- 生产 `/api/music/generate-async` 返回 `202 queued`。
- 后台 MiniMax 生成成功，并把 AI 曲目插入后续队列：
  - `ai-generated-63`
  - `ai-generated-64`
  - `ai-generated-65`
- 当前网易云歌曲保持不变，AI 曲目进入 queue，符合“生成歌曲加入后续队列、不替换当前歌曲”的设计。

问题：网易云基础歌匹配仍差，出现 `都选C`、`可爱女人` 等明显不适合现代职场场景的歌曲；AI 生成耗时期间 UI 反馈不够清楚。

### 创建与叙事

- 开场故事质量明显提升：杭州、AI协作工具、陆昊然、陈晓雨、林一凡均进入主线。
- 分段、标点、对话格式基本正常。
- 场景插画能生成，且开场/回合插画基本贴合故事。
- 人物收集不再是 0，基础收集识别到 6 人。
- 历史回顾能显示第 1 周周一记录和摘要。
- 设置按钮已恢复为设置菜单，不再误开剧情助手。

## 仍存在的问题

### P0：第 2 周入口空白阻断

复现步骤：
1. 新建游戏并完成开场。
2. 推进第 1 周周一、周中、周末。
3. 周总结后点击“继续人生旅途”。

结果：
- 后端已 `Advanced to 第2周` 并保存。
- 前端页面只显示顶部按钮、剧情助手和音乐播放器。
- 主故事区域没有 loading 文案、没有错误提示、没有第 2 周故事。
- 刷新后仍为空白，未触发新的第 2 周事件生成。

根因判断：
- `handleContinueAfterSummary` / `handleContinueToNextRound` 设置 `phase=loading` 后依赖 `generateEventRef.current()`。
- 若 phaseRef/generating 状态仍旧，`generateEvent` 会被自身 guard 挡住。
- 修复：继续流程调用 `generateEventRef.current({ force: true })`。
- 回归测试：`frontend/src/__tests__/hooks/useGameState.test.ts` 新增两条 stale phase 防空白测试。

### P1：创建阶段时代卡片和愿景冲突

用户愿景明确写“2020年代中国互联网产品经理”，第 1 步时代背景仍默认生成“713年唐代”。后续年龄/性别/世界观又回到现代，导致创建数据内部不一致。

### P1：故事节奏过快

第 1 周压入过多事件：周一早会、产品转型、评审、林一凡评估、周五合伙人会议、周六复盘、下周分享会预热。回合粒度和周内时间跨度不匹配。

### P1：时间线和季节冲突

开场是 2022 年夏季杭州，主游戏第 1 周变成 2022 年 1 月雪天。周总结中又出现“周日（第2周）”这类日期/周次混乱。

### P1：选项结构不稳定

多次复现：
- 第 2 周周中只生成 2 个选项：`陪晓雨去吃麻辣烫再干活` / `直接回家搭调研框架`。
- 第 3 周周末只生成 2 个选项，且 fallback 文案退化为 `回应眼前的请求` / `先核对现场线索`。

本轮已修：`OptionGenerator` 现在必须生成 3 个选项才算成功，fallback 也返回 3 个上下文相关选项；`StoryGenerator` 选项校验失败时不再返回硬编码泛化二选项。

### P1：音乐匹配仍弱

虽然增加了弱匹配过滤，但网易云检索仍大量命中爱情/流行歌曲，当前播放曲与场景不匹配。长流程中稳定出现：
- `都选C`
- `她说`
- `因为爱情有时差`
- `一直很安静`
- `童话`
- `丑八怪`

MiniMax 原创曲能入队，但用户要等当前网易云曲播完或手动切歌才能听到。建议后续把 AI 生成曲的播放优先级前移，或在现代职场场景下限制网易云候选为纯音乐/无歌词/影视配乐。

### P1：资源状态缺少玩法反馈

推进到第 3 周后精力降到 `0`，但游戏仍允许继续高强度推进，没有疲劳提示、恢复建议或失败风险。这会削弱资源系统的存在感。

### P1：长生成阶段体验仍慢

第 2 周周中、第 3 周周一、第 3 周周末均进入 1 分钟以上的逻辑校验/复杂推演阶段。虽然“恢复当前进度”兜底能避免空白，但缺少明确说明：当前是在校验、重写、生成选项、还是等场景图。

### P2：收集系统粒度仍需复查

初期人物收集可用但物品为 0；推进到第 3 周周总结后，后端开始提取关键物品：`SemantLink API文档U盘`、`林一凡的技术架构笔记`、`竞品分析报告`、`用户调研框架模板`、`里程碑计划初稿` 等。仍需复查 UI 是否同步展示这些新物品，以及智能识别是否继续推荐重复人物。

### P2：按钮语义仍可优化

“总结”主按钮会打开剧情助手并在其中生成总结。功能可用，但入口和展示位置容易被理解为按钮错位。

## 截图证据

截图目录：`docs/screenshots-2026-06-08-story101-deep/`

关键截图：
- `00-home.png` 首页
- `13-opening-story-generated.png` 开场故事
- `15-week1-story.png` 第 1 周周一
- `16-tts-warm-female.png` TTS 温柔女声
- `17-tts-calm-male.png` TTS 沉稳男声
- `18-tts-clear-neutral.png` TTS 清亮中性
- `24-collection.png` 人物收集
- `27-history.png` 历史回顾
- `39-week2-after-refresh.png` 第 2 周空白恢复失败
- `40-week2-event-recovered.png` 热部署后第 2 周恢复成功
- `41-reached-week4.png` 长流程到达第 4 周
- `42-week2-midweek-two-options.png` 第 2 周周中二选项问题

## 本轮已修

- 修复第 2 周入口空白的前端状态机问题。
- 修复选项生成稳定性：必须返回 3 个选项；fallback 不再使用泛化二选项。
- 新增回归测试：
  - `forces next event generation after weekly summary so stale phase cannot block it`
  - `forces next round generation after sync so stale phase cannot leave a blank play page`
  - `test_generate_options_rejects_two_options_and_returns_three_contextual_fallbacks`
  - `test_generate_round_event_option_failure_uses_three_contextual_fallbacks`
- 验证：
  - `cd frontend && npx jest src/__tests__/hooks/useGameState.test.ts --runInBand`
  - `cd frontend && npm run test:types`
  - `pytest tests/test_gate_gameplay_behavior_no_mock.py tests/test_fallback_events_contract.py tests/test_ai_extended.py::TestOptionGenerator tests/test_ai_extended.py::TestStoryGenerator -q`
