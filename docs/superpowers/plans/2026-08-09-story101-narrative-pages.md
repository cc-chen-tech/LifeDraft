# story101 创建、开场与结局页面实施计划

## 目标

在 `codex/story101-narrative-pages-20260809` 中完成全站墨色视觉系统的第三个独立 PR：统一角色创建、开场故事与结局仪式页面，使三个页面共享 story101 品牌、排版、表单、反馈、触控和移动端规则，同时严格保留已合入的生成、恢复、请求隔离和叙事加载契约。

## 基线与边界

- 基线：`origin/main@83e7792c09003ba43f9fc34bf71494817a94ee2e`（PR #275 merge commit）。
- 只改前端展示、布局、组件语法和对应测试；不改 backend、数据库、OpenAPI、store、API 参数、SSE、生成任务、恢复逻辑或请求次数。
- 不修改图片/头像生成器的业务状态和小型 loader；不修改 `ShareCard` 的导出 DOM、配色、尺寸或 html2canvas 行为。
- 保留开场首 chunk 前 screen、首 chunk 后正文文末 inline、失败后保留 partial、attempt/abort 隔离、空完成失败、可见文本完成后才可进入游戏。
- 保留结局 response normalization、gameId/requestId 隔离、15 秒 delayed、失败/重试和空响应处理。
- 保留创建流程五个真实步骤、自动背景真实步骤标签、预设保存、图片恢复和全部回调顺序。

## 设计与接口

### PageEdgeBookmark

```ts
interface PageEdgeBookmarkProps extends React.ComponentPropsWithoutRef<"aside"> {
  label: string;
  detail?: string;
}
```

- 只显示当前真实步骤/章节，不生成英文眉题、补零页码、版本号或虚构场景名。
- 桌面仅显示一个当前书签；移动端在正文顶部以普通步骤说明呈现，不隐藏任何操作。
- 书签是信息标记，不伪装成按钮；真实导航仍使用语义化 Button。

### 页面共同语法

- 使用 `PageTransition` 承载唯一一次 180–220ms 页面进入；reduced-motion 静止。
- 创建与结局每屏最多一个 reading Surface；内部内容使用分隔行而非卡片套卡。
- 所有输入使用 `FormField` 与真实 Input/Textarea，label、description、error、计数通过 `aria-describedby` 关联。
- 所有页面动作至少 44×44px；桌面/移动均保留返回、重试、开始、回顾与新人生等必要入口。
- 状态色只用于真实 success/warning/danger/info，普通按钮不使用大面积状态色。

## TDD 切片

### Task 1：共享书签与角色创建

1. 先补 `PageEdgeBookmark`、CreatePage、StepPlayerInfo、CompletionScreen、SettingFeedbackCard 与预设反馈的失败测试。
2. 创建页统一为小写 `story101`、单 reading Surface、真实当前步骤书签与带名称的步骤导航；删除发光圆点进度和旧 card/shadow 语法。
3. 姓名、愿景、重生成反馈与预设名迁移到 FormField；超限保持完整输入并关联错误，hook 的防御性 guard 不变。
4. 抽取单一 `PresetSaveSheet`，让互动页与完成页共用完全相同的 input-limit、saving/error 和提交契约；页面 toast 使用 FeedbackNotice，不得新增第二次提交、reload 或请求。
5. CompletionScreen 使用同一阅读轴和分隔区；图片生成组件业务与 loader 不动。

### Task 2：开场故事

1. 先补页面壳层、单 reading Surface、故事正文排版、44px 动作和无旧 visual noise 的失败测试；保留现有全部 streaming/race 测试。
2. 首段前仍只渲染 `NarrativeLoadingState layout="screen"`；首段后只渲染正文与文末 inline 状态，不返回整页态。
3. 已有故事、partial error、retry 和 complete 状态共用安静阅读轴；不增加伪章节号或预计时间。
4. 插画反馈输入迁移为真实 FormField/Textarea，插画生成逻辑、请求、图片和 loader 不改。
5. `OpeningCompletionGate` 只调整 story101 按钮/辅助文本视觉；backendComplete、visibleComplete、pending 和 onStart 语义不变。

### Task 3：结局仪式

1. 先补单 reading Surface、真实可用章节索引、关系/成就分隔行、44px、长中文和移动布局失败测试。
2. 结局标题、总结、关系、成就与回顾只根据 normalization 后真实字段渲染；不存在的章节不显示，不添加 editorial metadata。
3. `LifeReviewCard` 与 `AchievementBadge` 去除 nested Card/glow，将真实回顾字段呈现为分隔章节；ShareCard 子树不改。
4. 保持 loading/failed screen、retry、request ownership、malformed optional sanitization 和 new-game/reset 调用不变。

### Task 4：真实页面 E2E 与验收

1. 新增确定性 Playwright，覆盖创建初始/中间/完成、开场 initial/partial/ready/failed、结局 ready/failed；所有 mock 限同源精确 URL 与请求次数。
2. 1440×900、390×844 截图；320/375/390 无横向溢出，控件和对话框均位于 viewport/safe-area 内。
3. 断言每页最多一个 reading Surface、零 raised Surface、无 Story Life/glow/伪英文元数据、正文/操作不低于 14px、辅助信息不低于 12px、touch target 至少 44px。
4. 将 `/create`、`/story/opening` 与 `/ending` 纳入已有 AppShell 底部声音栏预算；通过真实滚动几何断言正文末端不会被常驻播放器遮挡，不改变播放器 store、播放列表或持久挂载语义。
5. 运行聚焦 Jest、`npm run test:types`、`npm run lint`、目标 Playwright、production build，最后运行 `./scripts/test-run-isolated.sh --namespace story101_narrative_pages all`。

## 完成条件

- 创建、开场、结局使用统一 story101 墨色语法，但叙事加载六色/文案/动效保持原样。
- 桌面只出现一个真实当前书签；移动端不隐藏必要入口，无竖排微字或伪页码。
- 无 glow、卡片套卡、大面积状态色、虚构英文眉题或无数据依据的章节编号。
- 正文出现后不返回整页 loading；结局请求失败可重试且旧请求不能回写新 game。
- 原有 API、回调参数、请求次数、store、生成与恢复路径不变。
