# Story101.live 深度体验复测报告

测试时间：2026-06-08 15:08-17:10（Asia/Shanghai）
测试环境：生产 `https://story101.live`
部署提交：`3385ed2839ab80cbdd8ec4fc183ea2a8f4e629e8` + PR 分支补丁 `1fdfa4ac` / `bc432580`
测试账号：本轮新注册账号（密钥截图仅作本地证据，不在报告中展开）
测试游戏：`game_id=95`，顾晨曦，2020年代中国互联网 / AI协作工具 / 产品经理成长线；已从创建流程推进到第 4 周。

## 结论

本轮生产已经包含 PR #51 的主要代码，MiniMax 环境变量生效，TTS 和音乐生成的核心后端链路都能跑通。

初次长流程在第 2 周入口复现空白主内容阻断。该问题已在本轮补回归测试并修复为：继续周总结/下一轮后强制触发事件生成，避免 stale phase/generating 状态挡住 `/event`。补丁热部署后，刷新同一个 `game_id=95` 能恢复第 2 周事件生成，并继续推进到第 4 周。

随后又在生产复现了选项数量不稳定问题：第 2 周周中和第 3 周周末出现二选项/泛化 fallback。已补后端回归测试并修复为：选项生成必须达到 3 个才算有效，fallback 也必须返回 3 个上下文相关选项。补丁 `bc432580` 热部署后，从第 4 周继续推进得到 3 个具体选项：`优先梳理白皮书数据`、`先找林一凡沟通技术进度`、`修改里程碑计划验收细节`。

## 部署与 CI 状态

- 生产 ECS `/opt/story2` 已部署到 `3385ed2839ab80cbdd8ec4fc183ea2a8f4e629e8`，并热打 PR 分支补丁 `1fdfa4ac` 的前端状态机修复和 `bc432580` 的三选项 fallback 修复。
- 生产健康检查通过：`/api/health` 和 `/health` 正常。
- GitHub PR #51 checks 仍红，但 GitHub run/job 没有 runner/steps，`gh run view --log` 返回 `log not found`。Actions API 显示失败 job 的 `runner_name=""`、`steps=[]`。这不是本地测试失败形态，仍属于 CI/runner 层面的发布不稳定因素。
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

本轮已修：
- `loading` 状态下主按钮改为禁用的“正在准备朗读”，并显示加载图标。
- `playing` 状态下主按钮改为禁用的“正在朗读”，不再显示可再次点击的“朗读当前故事”。
- “继续朗读”只在 `paused` 状态出现，避免 idle/loading 阶段误导用户。
- 回归测试：
  - `labels backend audio preparation instead of offering another read action`
  - `labels active backend audio playback instead of showing the idle read action`
- 红灯复现：旧组件在 `loading` 和 `playing` 下仍暴露“朗读当前故事”按钮。
- 本地验证：`cd frontend && npx jest src/__tests__/components/StoryVoiceControls.test.tsx --runInBand`、`./test.sh preflight` 均通过。
- 生产复测：
  - 补丁 `cfbb19d5` 热部署并重建 frontend 后，公网 `/api/health` 和 `/health` 正常。
  - browser-agent 打开 `https://story101.live/e2e-regression`，故事朗读控件正常加载，准备中/播放中文案由组件红绿回归测试覆盖。

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

## 已修复并生产复测通过

### 第 2 周入口空白阻断

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
- 生产复测：热部署后刷新同一游戏，能恢复第 2 周事件生成，并继续推进到第 4 周。

### 选项结构不稳定

复现步骤：
1. 在同一个生产游戏中推进到第 2 周周中或第 3 周周末。
2. 等待故事生成完成。

结果：
- 第 2 周周中只生成 2 个选项：`陪晓雨去吃麻辣烫再干活` / `直接回家搭调研框架`。
- 第 3 周周末只生成 2 个选项，且 fallback 文案退化为 `回应眼前的请求` / `先核对现场线索`。

根因判断：
- 选项生成器允许 `len(options) >= 2` 通过。
- `StoryGenerator` 的异常 fallback 使用硬编码二选项，且丢失具体故事上下文。

修复：
- `OptionGenerator` 现在必须生成 3 个选项才算成功，过多选项会截断到 3 个，少于 3 个会重试。
- fallback 返回 3 个上下文相关选项，不再使用泛化二选项。
- `StoryGenerator` 选项校验失败时保留已生成故事文本，并用上下文 fallback 补足 3 个选项。
- 生产复测：`bc432580` 热部署后，第 4 周继续推进得到 3 个具体选项。证据截图：`43-week4-three-specific-options.png`。

## 仍存在的问题

### P1：创建阶段时代卡片和愿景冲突

用户愿景明确写“2020年代中国互联网产品经理”，第 1 步时代背景仍默认生成“713年唐代”。后续年龄/性别/世界观又回到现代，导致创建数据内部不一致。

本轮已修：
- era prompt 增加强约束：人生愿景里的年份、年代、国家/地区、行业、职业是硬约束，不能被改写为古代或无关时代。
- 后端增加确定性校验：如果愿景明确是现代互联网/产品经理/AI/公司等职业线，但 AI 返回古代年份或唐宋元明清等古代 cue，会自动纠正为现代中国互联网行业背景。
- 回归测试：`test_generate_era_honors_explicit_modern_product_manager_life_vision` 覆盖 AI 返回唐代时的纠偏。
- 生产复测：`/api/character/setting` 对“2020年代中国互联网公司，成为AI协作工具产品经理”返回 `year=2024`，描述包含 AI / 互联网 / 产品经理，未出现唐代或古代 cue。

### P1：故事节奏过快

第 1 周压入过多事件：周一早会、产品转型、评审、林一凡评估、周五合伙人会议、周六复盘、下周分享会预热。回合粒度和周内时间跨度不匹配。

本轮已修：
- 普通周故事和三轮故事 prompt 均新增“回合节奏硬约束”。
- 明确要求每个回合只推进一个主事件、只设置一个核心决策点。
- 明确禁止在同一回合塞入多个会议、评审、复盘、预热、发布、下周安排等不相干事件。
- 明确禁止把下一周或下一个回合的实际剧情提前写完；后续事项最多作为一句背景伏笔。
- 回归测试：`test_story_prompts_limit_each_round_to_one_main_event`。
- 红灯复现：新增测试在旧 prompt 下失败，缺少“每个回合只推进一个主事件”。
- 本地验证：`pytest tests/test_gate_gameplay_behavior_no_mock.py -q`、`pytest tests/test_ai_extended.py -q`、`./test.sh preflight` 均通过。
- 生产复测：
  - 补丁 `ad2c0f90` 热部署并重建 backend 后，生产容器 healthcheck 为 healthy，公网 `/api/health` 和 `/health` 正常。
  - 生产容器内 prompt smoke 已确认普通周故事和三轮故事 prompt 均包含“每个回合只推进一个主事件”“只设置一个核心决策点”“禁止在同一回合塞入多个会议、评审、复盘、预热”“禁止把下一周或下一个回合的实际剧情提前写完”。

### P1：时间线和季节冲突

开场是 2022 年夏季杭州，主游戏第 1 周变成 2022 年 1 月雪天。周总结中又出现“周日（第2周）”这类日期/周次混乱。

本轮已修一部分：
- 开场故事 prompt 增加“开场时间硬约束”，默认锚定到 `era.year` 的 `1月第1周（冬季）`，与 `PlayerState.get_game_date_info()` 的第 1 周日期一致。
- prompt 明确要求开场故事和主游戏第 1 周从同一时间继续，天气、季节、日期不得冲突，并对本次复现的“夏季”增加直接禁止语句。
- 回归测试：`test_opening_story_prompt_anchors_first_week_date_and_season`。

生产复测：
- 补丁 `19b7ddd3` 热部署并重建后端后，生产容器内 prompt smoke 已确认输出：
  - `2024年1月第1周（冬季）`
  - `开场故事和主游戏第1周必须从这个时间继续`
  - `特别禁止写成夏季`
- 公网 `/api/health` 和 `/health` 正常，后端容器 healthcheck 为 healthy。

状态：开场时间锚点已热部署并通过生产 prompt smoke；仍需新开场故事长流程复查实际生成文本。

周总结边界补充修复：
- 周总结 prompt 增加“周总结时间边界”，明确只覆盖当前周的周一、周中、周末三个回合。
- prompt 明确禁止把下一周写进本周总结，尤其禁止“周日（第2周）”这类把本周周末推进到下一周的表达。
- 回归测试：`test_weekly_summary_prompt_forbids_next_week_day_mismatch`。
- 本地验证：`pytest tests/test_gate_gameplay_behavior_no_mock.py -q`、`pytest tests/test_ai_extended.py -q`、`pytest tests/test_api_gameplay.py::TestGenerateSummary -q`、`./test.sh preflight` 均通过。
- 生产复测：
  - 补丁 `bbe9a85b` 热部署并重建后端后，生产容器 healthcheck 为 healthy，公网 `/api/health` 和 `/health` 正常。
  - 生产容器内 prompt smoke 已确认输出“本总结只覆盖2024年1月第1周”“不得把下一周写进本周总结”“禁止写成“周日（第2周）””。

### P1：音乐匹配仍弱

虽然增加了弱匹配过滤，但生产长流程中仍大量命中爱情/流行歌曲，当前播放曲与场景不匹配。长流程中稳定出现：
- `都选C`
- `她说`
- `因为爱情有时差`
- `一直很安静`
- `童话`
- `丑八怪`

根因判断：
- 当 AI 音乐分析返回泛化结果时，音乐服务没有从故事正文补充“产品经理 / 用户数据 / AI协作 / 会议室”等确定性职场 cue。
- MiniMax 原创曲插入到网易云下一曲之后，用户要等两首歌或手动切歌才能听到故事定制曲。

本轮已修：
- 音乐服务会从故事正文和角色设定补充现代职场上下文，并把 `都选C`、`她说`、`因为爱情有时差`、`一直很安静`、`童话`、`丑八怪`、`可爱女人` 等弱匹配流行歌加入职场负面 cue。
- MiniMax 生成曲不再插到网易云下一曲之后；它会在不打断当前播放的前提下成为下一首。
- 修复“用户数据”误触发医疗悬疑搜索的问题：单独的数据/用户数据不再生成 `现代医院`、`医疗悬疑` 等搜索词，只有医疗/医院/造假等真实悬疑医疗上下文才会触发。
- 修复网易云严格过滤后为空的边界：如果当前没有正在播放的歌曲，MiniMax 生成曲会直接成为 current song，而不是只落到 queue 里等用户手动切歌。
- 继续修复一个 UI 同步遗漏：MiniMax 生成曲进入 playlist queue 后，`MusicPlayer` 的可见推荐列表仍可能停留在旧 `recommendation.songs`，导致用户看不到 AI 曲已经成为后续队列。
- 现在所有 playlist 同步路径都会把 `recommendation.songs` 更新为 `[current_song, ...queue]`，播放器列表、当前曲和后续队列保持一致。
- 回归测试已覆盖：AI 分析泛化时仍过滤 `都选C`，并推荐 `办公室 轻电子 氛围`；同步覆盖后端 API / DB / 前端 store 队列顺序。
- 回归测试补充：`带 music_brief 的故事推荐会后台生成 AI 音乐并从播放列表插入后续队列` 现在断言 UI 中可见 `AI MiniMax 雨夜追逐`。
- 红灯复现：旧逻辑下 store queue 已包含 `AI MiniMax 雨夜追逐`，但播放器 DOM 中找不到该曲名。
- 生产复测：
  - `game_id=95` 中保留当前播放不变，MiniMax 异步生成完成后 `ai-generated-77` 成为 queue[0]。
  - 临时 `game_id=96` 初始 `current_song=null`、`queue=[]`，MiniMax 异步生成完成后 `ai-generated-79` 成为 current song；验证后已删除临时游戏。
  - 现代职场推荐 smoke 不再生成 `现代医院` / `医疗悬疑` 搜索词，也未返回 `都选C` 等弱匹配歌名。
  - 补丁 `28a3391f` 热部署并重建 frontend 后，公网 `/api/health` 和 `/health` 正常。
  - browser-agent 打开 `https://story101.live/e2e-regression`，音乐回归夹具和 MiniMax 触发入口正常加载；AI 曲进入 playlist 后同步显示到播放器列表的核心行为由组件红绿回归测试覆盖。

### P1：资源状态缺少玩法反馈

复现结果：
- 生产长流程推进到第 3 周后，精力降到 `0`。
- 游戏仍允许继续高强度推进，结果页没有疲劳提示、恢复建议或失败风险。
- 后端状态值会被 `PlayerState.update` 夹到 `0`，但 choice result 的 `effects_applied` 仍返回原始高消耗值，前端因此无法解释“为什么精力已经 0 还继续扣 -20”。

本轮已修：
- choice processor 在应用效果前计算 `effects_requested` 和实际生效的 `effects_applied`。
- 当精力/情绪/学识/财富触底或触顶时，返回 `resource_warnings`，例如“精力不足，实际变化为 -5”。
- 叙事续写、历史记录、decision history 和 API 返回均使用实际生效效果，同时保留请求效果用于解释。
- 前端 result 阶段会把 `resource_warnings` 合并到本轮结果摘要的“资源提示”区域，避免静默继续。
- 回归测试：
  - `test_exhausting_choice_reports_actual_applied_energy_and_warning`
  - `test_zero_energy_exhausting_choice_applies_no_extra_energy_loss`
  - `appends resource warnings to the round summary`
  - `shows resource warnings even when the backend summary is empty`

生产复测：
- 补丁 `839193b7` 热部署后，注册临时 smoke 账号并创建临时 `game_id=96`。
- 将当前事件植入为：精力 `5`，选项消耗 `energy=-20`。
- 调用公网 `/api/games/96/choice-sync` 返回：
  - `effects_applied.energy=-5`
  - `effects_requested.energy=-20`
  - `resource_warnings[0].message=精力不足，实际变化为 -5`
- 临时测试游戏已清理。

状态：已热部署并通过生产 API smoke；完整 UI 结果页展示仍可在下一轮长流程中复查。

### P1：长生成阶段体验仍慢

第 2 周周中、第 3 周周一、第 3 周周末均进入 1 分钟以上的逻辑校验/复杂推演阶段。虽然“恢复当前进度”兜底能避免空白，但缺少明确说明：当前是在校验、重写、生成选项、还是等场景图。

本轮已修：
- 当已有部分故事正文、但仍处于 `generating` / `choosing` 阶段超过 60 秒时，页面会显示“已等待 X，正在校验故事逻辑和生成选项”的说明。
- 长等待说明明确告知用户这是长剧情一致性检查，不代表内容丢失。
- 同一提示区提供“恢复当前进度”按钮，调用现有 `recoverEventGeneration`，不需要刷新页面。
- 回归测试：`explains long-running generation when partial story text already exists`。
- 本地验证：`cd frontend && npx jest src/__tests__/pages/PlayPage.test.tsx --runInBand`、`./test.sh preflight` 均通过。
- 生产复测：
  - 补丁 `ddf382a9` 热部署并重建 frontend 后，公网 `/api/health` 和 `/health` 正常。
  - browser-agent 打开 `https://story101.live/e2e-regression`，页面正常加载；长等待提示的触发条件由 PlayPage 回归测试覆盖。

### P2：收集系统粒度仍需复查

初期人物收集可用但物品为 0；推进到第 3 周周总结后，后端开始提取关键物品：`SemantLink API文档U盘`、`林一凡的技术架构笔记`、`竞品分析报告`、`用户调研框架模板`、`里程碑计划初稿` 等。仍需复查 UI 是否同步展示这些新物品，以及智能识别是否继续推荐重复人物。

本轮已修：
- 自动收集不再要求人物/物品/地点三类全为空才运行。即使人物已经存在、物品仍为空，也会继续触发实体识别并补充缺失物品。
- 自动添加前按当前收集列表过滤同名人物、物品和地点，避免把已经收集过的人物再次提交给 `add-entities`。
- 继续修复一个遗漏：`autoCollectRecognizedEntities` 之前按 `gameId` 只允许自动识别一次。第 1 周补过人物后，第 3/4 周新出现的 U 盘、API 文档、竞品报告等物品不会再自动识别。
- 现在只保留 in-flight 去重，避免并发重复请求，但允许同一个游戏后续剧情继续触发自动识别和补齐新物品。
- 回归测试：`auto-collects missing item entities when characters already exist`。
- 回归测试补充：`continues auto collection after later story rounds introduce new items`。
- 红灯复现：新增测试在旧逻辑下只发出 1 次 `/recognize-entities`，第二次自动收集被 game-level attempted guard 挡住。
- 本地验证：`cd frontend && npx jest src/__tests__/stores/useCollectionStore.test.ts --runInBand`、`./test.sh preflight` 均通过。
- 生产复测：
  - 补丁 `3c32ec41` 热部署并重建 frontend 后，公网 `/api/health` 和 `/health` 正常。
  - browser-agent 打开 `https://story101.live/e2e-regression`，页面正常加载并显示“收集”入口；自动补齐缺失实体类别的核心行为由 store 回归测试覆盖。
  - 补丁 `3e6132cf` 热部署并重建 frontend 后，公网 `/api/health` 和 `/health` 正常。
  - browser-agent 再次打开 `https://story101.live/e2e-regression`，页面正常加载并显示“收集”入口；后续剧情新物品持续自动识别的核心行为由 store 红绿回归测试覆盖。

### P2：按钮语义仍可优化

“总结”主按钮会打开剧情助手并在其中生成总结。功能可用，但入口和展示位置容易被理解为按钮错位。

本轮已修：
- 快捷动作和展开面板里的按钮从“总结”改为“人生总结”，避免和普通剧情助手聊天混淆。
- 生成总结时不再向聊天历史追加“请总结我的人生故事”这类伪用户提问，只显示后端返回的人生总结内容。
- 回归测试：`presents summary as a dedicated action instead of a fake chat prompt`。
- 本地验证：`cd frontend && npx jest src/__tests__/components/ChatBar.test.tsx --runInBand`、`./test.sh preflight` 均通过。
- 生产复测：
  - 补丁 `4e55d8b2` 热部署并重建 frontend 后，公网 `/api/health` 和 `/health` 正常。
  - browser-agent 打开 `https://story101.live/e2e-regression`，收起态和展开态均显示“人生总结”按钮。
  - 点击“人生总结”后 DOM 中没有旧的“请总结我的人生故事”伪聊天提问；该 e2e 页面没有真实游戏会话，因此总结 API 返回错误提示，但按钮语义和展示路径已生效。

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
- `43-week4-three-specific-options.png` 三选项修复后生产复测

## 本轮已修

- 修复第 2 周入口空白的前端状态机问题。
- 修复选项生成稳定性：必须返回 3 个选项；fallback 不再使用泛化二选项。
- 修复音乐队列优先级：MiniMax 生成曲作为下一首入队，不再排在网易云下一曲之后。
- 修复现代职场音乐过滤：从故事正文补充职场 cue，避免 AI 分析泛化时推荐弱匹配流行歌。
- 修复资源反馈：低精力时 `effects_applied` 反映实际生效变化，后端返回 `resource_warnings`，前端结果页展示资源提示。
- 修复开场时间锚点：开场故事与主游戏第 1 周使用同一日期/季节约束，避免开场夏季、第一周冬季的冲突。
- 新增回归测试：
  - `forces next event generation after weekly summary so stale phase cannot block it`
  - `forces next round generation after sync so stale phase cannot leave a blank play page`
  - `test_generate_options_rejects_two_options_and_returns_three_contextual_fallbacks`
  - `test_generate_round_event_option_failure_uses_three_contextual_fallbacks`
  - `test_generated_track_insertion_makes_ai_music_next_after_current`
  - `test_music_service_derives_workplace_filter_from_story_when_ai_analysis_is_generic`
  - `test_exhausting_choice_reports_actual_applied_energy_and_warning`
  - `test_zero_energy_exhausting_choice_applies_no_extra_energy_loss`
  - `appends resource warnings to the round summary`
  - `shows resource warnings even when the backend summary is empty`
  - `test_opening_story_prompt_anchors_first_week_date_and_season`
- 验证：
  - `cd frontend && npx jest src/__tests__/hooks/useGameState.test.ts --runInBand`
  - `cd frontend && npx jest src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts --runInBand`
  - `cd frontend && npm run test:types`
  - `pytest tests/test_gate_gameplay_behavior_no_mock.py tests/test_fallback_events_contract.py tests/test_ai_extended.py::TestOptionGenerator tests/test_ai_extended.py::TestStoryGenerator -q`
  - `pytest tests/test_story_music_recommendation_contract.py tests/test_minimax_audio_generation_contract.py::test_music_generate_api_persists_generated_track_into_future_playlist_queue tests/test_minimax_audio_generation_contract.py::test_music_generate_async_api_returns_quickly_and_persists_future_playlist_track tests/test_minimax_audio_generation_db.py::test_ready_minimax_music_asset_inserts_as_next_playlist_track -q`
  - `pytest tests/test_choice_processor_contract.py -q`
  - `pytest tests/test_gate_gameplay_behavior_no_mock.py -q`
  - `cd frontend && npx jest src/__tests__/hooks/choiceUtils.test.ts --runInBand`
  - `./test.sh preflight`
