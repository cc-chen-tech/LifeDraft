# MusicPlayer 进度同步节流修复（2026-06-10）

## 问题背景

用户反馈音乐播放时偶发卡顿，根因之一是 `audio.ontimeupdate` 每次触发都立即写入全局 `currentTime`。  
`timeupdate` 在浏览器中会高频触发（通常 40~250ms 一次），频繁更新 Zustand store 导致：

- 全局状态抖动、重复渲染；
- 与进度条/展示面板同步链路被放大；
- 在某些设备上导致后续队列推进/切歌逻辑响应变慢。

## 复现步骤（问题先导）

1. 打开故事播放页，确保 `MusicPlayer` 可见并进入播放状态。  
2. 观察 `MusicPlayer` 内部 `audio` 元素的 `timeupdate` 触发链路（在测试层面通过 mock audio 复现）。  
3. 连续触发多个 `ontimeupdate`（例如 10 次，间隔 40ms）时，当前实现会同步 10 次 `setCurrentTime`。

## 测试补齐（多层）

- 单元组件测试：`frontend/src/__tests__/components/game/MusicPlayer.test.tsx`
  - 新增 `高频 timeupdate 只同步有限次数到全局 currentTime，但即时展示依然响应`：
    - 不 mock 音频接口行为语义，仅复用既有 `MockAudioClass`；
    - 验证 `0:10` 的展示会随本地状态即时变化；
    - 验证全局 `setCurrentTime` 调用次数被 250ms 节流显著压缩。
- 已有回归单测补充：`MusicPlayer timeupdate 节流`（文件内纯逻辑测试）用于阐明节流边界逻辑。

## 修复实现

文件：`frontend/src/components/game/MusicPlayer.tsx`

1. 引入局部展示状态：
   - `displayCurrentTime`：用于 UI 实时展示（左侧时间和 Slider 受控值）。
   - `lastCurrentTimeStoreSyncRef`：记录上一次同步到全局 `setCurrentTime` 的时间戳。

2. `audio.ontimeupdate` 改造：
   - 每次 `timeupdate` 都先写入 `displayCurrentTime`，保持进度条响应；
   - 每 250ms 最多同步一次全局 `setCurrentTime`，降低跨组件重渲染压力。

3. `audio.onended` 同步：
   - 同时清零局部显示和全局时间，防止结束后显示残留。

4. `handleSeek` 与 `currentTime` 同步副作用：
   - 拖拽进度更新时同时更新局部 `displayCurrentTime`；
   - 当全局 `currentTime` 被外部更新（如恢复播放）时，局部值兜底同步。

5. store 读取方式收敛：
   - 由一次性解构改为 `useMusicStore(selector)` 多次订阅，进一步减少不必要重渲染链路。

## 验证

- `./test.sh preflight`
  - 结果：通过（含 62 个 OpenSpec 校验项、125 条 Python 预检、前端 strict typecheck、24 套前端前置回归 Jest）。
- `cd frontend && npx jest src/__tests__/components/game/MusicPlayer.test.tsx --runInBand`
  - 结果：1 个测试套件通过，24 条用例全部通过。

## 结论

该问题已闭环修复：进度条展示保持流畅，且全局 `currentTime` 不再被每帧驱动更新。  
与音乐播放状态管理、切歌/排队逻辑的耦合风险显著下降，同时保留了对当前时间显示与用户交互（拖拽进度）一致性。
