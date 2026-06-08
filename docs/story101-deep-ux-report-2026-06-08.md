# Story101.live 深度体验复测报告

测试时间：2026-06-08 15:08-16:05（Asia/Shanghai）
测试环境：生产 `https://story101.live`
部署提交：`3385ed2839ab80cbdd8ec4fc183ea2a8f4e629e8`
测试账号：本轮新注册账号（密钥截图仅作本地证据，不在报告中展开）
测试游戏：`game_id=95`，顾晨曦，2020年代中国互联网 / AI协作工具 / 产品经理成长线

## 结论

本轮生产已经包含 PR #51 最新代码，MiniMax 环境变量生效，TTS 和音乐生成的核心后端链路都能跑通。

但长流程仍未能玩到第 4 周：第 1 周结束进入第 2 周后，页面进入空白主内容状态，只剩顶部按钮、剧情助手和音乐播放器；刷新后仍不能自动恢复生成第 2 周事件。该问题已在本轮补回归测试并修复为：继续周总结/下一轮后强制触发事件生成，避免 stale phase/generating 状态挡住 `/event`。

## 部署与 CI 状态

- 生产 ECS `/opt/story2` 已部署到 `3385ed2839ab80cbdd8ec4fc183ea2a8f4e629e8`。
- 生产健康检查通过：`/api/health` 和 `/health` 正常。
- GitHub PR #51 checks 仍红，但 GitHub run/job 没有 runner/steps，`gh run view --log` 返回 `log not found`。这不是本地测试失败形态。
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

第 1 周周末只生成了 2 个选项，而不是常规 3 个选项。后端日志显示选项 consistency validator 报错，但仍继续返回。

### P1：音乐匹配仍弱

虽然增加了弱匹配过滤，但网易云检索仍大量命中爱情/流行歌曲，当前播放曲与场景不匹配。MiniMax 原创曲能入队，但用户要等当前网易云曲播完或手动切歌才能听到。

### P2：收集系统粒度不足

人物收集可用，但“转型思路文件、竞品分析报告、技术评估报告、知识图谱工具”等物品/关键资产没有进入物品收集。智能识别只识别出已存在人物顾远航，疑似重复推荐。

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

## 本轮已修

- 修复第 2 周入口空白的前端状态机问题。
- 新增回归测试：
  - `forces next event generation after weekly summary so stale phase cannot block it`
  - `forces next round generation after sync so stale phase cannot leave a blank play page`
- 验证：
  - `cd frontend && npx jest src/__tests__/hooks/useGameState.test.ts --runInBand`
  - `cd frontend && npm run test:types`

