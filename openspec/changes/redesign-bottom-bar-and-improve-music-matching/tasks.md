## 1. Test Gates First (TDD)

- [x] 1.1 新增 ChatBar UI 契约测试：收起态只显示 💬 圆形按钮，无独立"改写"按钮
- [x] 1.2 新增 ChatBar 展开态契约测试：改写按钮触发内联 Sheet，Sheet 包含输入框和"改写故事"按钮
- [x] 1.3 新增 GlobalMusicPlayer 位置回归测试：top-0 定位，不到 bottom-0
- [x] 1.4 新增 play/page 契约测试：不再 import StoryAdjuster，ChatBar 接收 storyText/onRewriteComplete props
- [x] 1.5 新增音乐分析完整文本契约测试：service 层不截断 story_text
- [x] 1.6 新增搜索词多维度构造契约测试
- [x] 1.7 新增搜索结果相关性排序契约测试
- [x] 1.8 新增 E2E 浏览器测试：移动端底部无音乐播放器条、ChatBar 收起无改写按钮、改写内联 Sheet 正常工作
- [x] 1.9 更新 `test.sh`：接入所有新测试到对应层级

## 2. ChatBar 精简

- [x] 2.1 删除 ChatBar 收起态的独立"改写"按钮，只保留 💬 圆形按钮
- [x] 2.2 ChatBar 展开态"改写"按钮改为打开内联改写 Sheet
- [x] 2.3 内联改写 Sheet 复用原 StoryAdjuster 的核心逻辑（SSE 流式改写、toast、取消）
- [x] 2.4 ChatBar props：新增 `storyText`、`onRewriteComplete`，删除 `onAdjustStory`
- [x] 2.5 展开态"重新生成"按钮保持原有 SSE 流式重新生成行为

## 3. StoryAdjuster 删除

- [x] 3.1 从 `play/page.tsx` 移除 StoryAdjuster import 和 JSX
- [x] 3.2 移除 `showAdjuster` / `setShowAdjuster` 状态
- [x] 3.3 移除 `handleAdjustStory` 回调
- [x] 3.4 删除 `frontend/src/components/game/StoryAdjuster.tsx` 文件
- [x] 3.5 删除 `frontend/src/__tests__/components/StoryAdjuster.test.tsx`

## 4. GlobalMusicPlayer 上移

- [x] 4.1 迷你条从 `bottom-0` 改为 `top-0`，添加 `safe-area-pt` 和 margin-top 避开 status bar
- [x] 4.2 展开方向反转：从向上弹出改为向下展开
- [x] 4.3 Chevron 图标方向反转（收起 ▲ 展开 ▼）
- [x] 4.4 桌面端保持原有 `md:bottom-4 md:left-auto md:right-4 md:w-80` 行为

## 5. 音乐匹配改进

- [x] 5.1 移除 `_analyze_story_mood()` 中的文本截断
- [x] 5.2 增强 AI 分析 prompt：要求返回 mood、scene_type、era、pacing、energy、instruments
- [x] 5.3 搜索词构造结合多维度字段
- [x] 5.4 实现简单相关性排序（歌名/专辑/艺人 vs brief 关键词匹配）
- [x] 5.5 确保 AI 生成曲目只进入后续队列

## 6. Verification

- [x] 6.1 `./test.sh mypy` 通过
- [x] 6.2 `./test.sh imports` 通过
- [x] 6.3 `./test.sh contract` 通过（含新测试）
- [x] 6.4 `./test.sh db` 通过
- [x] 6.5 `./test.sh e2e` core 通过
- [x] 6.6 `cd frontend && npx tsc --noEmit --strict` 通过
- [x] 6.7 手动验证：移动端底部无重叠、改写内联 Sheet 工作、音乐条在顶部
