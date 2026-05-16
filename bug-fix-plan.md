# Bug Fix Plan — LifeDraft Production Issues

## A. 音乐卡顿问题 (P0 — 用户当前反馈)

### 根因分析
当前代码已部署两项修复（chunk_size 8KB + timeupdate 500ms 节流），但音乐在 story101.live 仍然卡顿。排查发现：

1. **Zustand 全量订阅导致过度重渲染**：MusicPlayer.tsx:36-59 使用 `useMusicStore()` 一次性解构全部状态。任何状态变更（volume、currentTime 等）都会触发整棵组件树重渲染。
2. **fadeVolume 每 50ms 更新 store**：useMusicStore.ts:156-176 的 `fadeInterval` 每 50ms 调用 `set({ volume: newVolume })`，即 **20 次重渲染/秒**。
3. **timeupdate 节流 500ms 仍有余量**：虽然从 250ms 提升到 500ms，但每次触发仍调用 `setCurrentTime(audio.currentTime)`，更新 Zustand store，触发全量重渲染。
4. **音频流本身的缓冲问题**：后端通过 `response.aiter_bytes(chunk_size=8192)` 转发 CDN 流。如果 CDN→ECS 链路延迟高，8KB chunk 仍可能产生缓冲 underrun。

### 修复方案
1. **拆分 Zustand selector**：MusicPlayer 改为按字段订阅，避免 volume/currentTime 变化触发全量重渲染。
2. **fadeVolume 改为直接操作 DOM，不经过 store**：音量渐变只修改 `audioElement.volume`，不调用 `set({ volume })`，需要时通过防抖/节流同步回 store。
3. **timeupdate 也改为直接操作 ref**：进度条更新使用 local ref + `requestAnimationFrame`，只在用户交互（seek/drag）时同步到 store。
4. **增加音频预缓冲策略**：audio 元素添加 `preload="auto"` + `buffered` 监控， stalled/waiting 时自动加大缓冲阈值或切换 URL。
5. **生产验证**：检查 ECS 上部署的 docker image 是否包含 dc81f77 和 edc7b4c 这两个 commit（通过容器内 git log 或文件 md5 校验）。

---

## B. 截图 Bug 清单分析 (P1)

### Bug 1: 故事文本重复显示
**状态**：仍存在  
**根因**：`streamRemainingText` 在 SSE 流结束后，把后端返回的完整故事文本追加到前端已经拥有的完整文本上，导致重复。  
**修复**：在 `streamRemainingText` 调用前，对比前后文本重叠度（如后缀匹配），若已有则跳过追加。

### Bug 2: 流式文字"闪一下"然后大量文字出现
**状态**：仍存在  
**根因**：Typewriter 效果 interval 为 30ms 每帧显示 2 字符，但 SSE 推送速度远高于此。`isStreaming` 状态切换时，文本从"打字中"瞬间变为完整文本，产生"闪一下"的视觉效果。  
**修复**：① 增加打字机缓冲区队列，按固定速率消费；② 或改为平滑滚动显示（CSS transition + clip），而非字符逐个 append。

### Bug 3: 文字出现删除线（~~strikethrough~~）
**状态**：仍存在  
**根因**：`stripIncompleteMarkdown` 未处理 `~~`（strikethrough）语法。流式输出中未闭合的 `~` 被 ReactMarkdown 渲染为删除线。  
**修复**：在 `stripIncompleteMarkdown` 中增加对 `~~` 的检测，若存在奇数个或未闭合的 `~~`，则转义或移除。

### Bug 4: 选择时不显示图片 / 两张图片都堆在底部
**状态**：仍存在  
**根因**：result 阶段同时渲染了 `eventSceneImage` 和 `resultSceneImage`，没有根据 `stage` 参数做互斥隐藏。  
**修复**：在 `result` phase 只显示 `resultSceneImage`，`eventSceneImage` 在 `stage === "event"` 时才渲染。

### Bug 5: 点击选择后文字发生变化
**状态**：仍存在  
**根因**：选择后 `setStoryText(result.story_continuation)` 用 continuation 替换了全部文本，而非追加。如果 continuation 包含对前文的改写/总结，视觉上就是"文字变了"。  
**修复**：改为追加模式 `setStoryText(prev => prev + result.story_continuation)`，或确保后端返回的 continuation 是纯粹的新增段落。

### Bug 6: 网络恢复后无法继续
**状态**：仍存在  
**根因**：SSE parser 在流结束时若未收到 `complete` 事件，会调用 `onComplete({})` 并关闭连接；没有自动重连逻辑。  
**修复**：① SSE 连接增加 `onerror` 自动重连（指数退避）；② 未收到 complete 时主动 poll 一次 `/api/games/{id}/state` 补齐数据。

### Bug 7: 跨场景图片重复
**状态**：仍存在  
**根因**：SceneImage 表缺少 `(game_id, round_number, stage)` 唯一索引，并发请求时可能重复写入。  
**修复**：① 数据库增加唯一约束/索引；② 写入前用 `INSERT ... ON CONFLICT DO UPDATE` 或 `get_or_create` 模式。

### Bug 8: 图片加载不出来
**状态**：仍存在  
**根因**：① 异步生成有 gap（202 Accepted 后图片还没生成完）；② SSE 推送的记录 `scene_id: 0`（未关联到正确 scene）；③ ECS 重新部署后存储卷丢失导致文件不存在。  
**修复**：① 图片生成改为同步等待或后台轮询进度；② 修正 SSE 消息中 scene_id 的绑定逻辑；③ 确认 storage 使用持久化卷（EBS/EFS），非容器内临时目录。

### Bug 9: 其他未分类问题
截图中可能还有 UI 布局、字体渲染、动画闪烁等问题，需在逐一验证后补充。

---

## C. 实施顺序

| 优先级 | 问题 | 预估工时 | 验证方式 |
|--------|------|----------|----------|
| P0 | 音乐卡顿 — Zustand selector 优化 | 2h | 浏览器 Performance 面板，帧率保持 60fps |
| P0 | 音乐卡顿 — fadeVolume 去 store | 1h | 音量渐变时 React DevTools Profiler 无渲染 |
| P1 | Bug 3 删除线 — stripIncompleteMarkdown | 1h | 单元测试 + 流式文本截图对比 |
| P1 | Bug 4 图片重复渲染 — stage 互斥 | 1h | 选择时只显示一张图片 |
| P1 | Bug 5 文字变化 — 追加模式 | 1h | E2E 断言选择后文本为 append 非 replace |
| P1 | Bug 6 网络恢复 — SSE 重连 | 2h | 断网/恢复模拟测试 |
| P2 | Bug 1 重复文本 | 2h | E2E 流式结束断言 |
| P2 | Bug 2 闪字 | 2h | 视觉回归测试 |
| P2 | Bug 7/8 图片重复/加载 | 3h | DB 约束 + storage 持久化确认 |
