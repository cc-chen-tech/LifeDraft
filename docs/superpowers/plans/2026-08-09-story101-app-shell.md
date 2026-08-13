# story101 App Shell、门户与资料库实施计划

## 目标

在 `codex/story101-app-shell-20260809` 中完成全站墨色视觉系统的第二个独立 PR：建立持久 AppShell，统一首页与认证、存档和角色预设，并让全局声音条在这些已迁移页面中占用真实固定区域预算。保持认证、存档、预设、音乐、朗读的 API、store、回调顺序和跨路由持久语义不变。

## 基线与边界

- 基线：`origin/main@2fc359333761932b22237bd2dbaf043cc3fa5f0c`（PR #269 merge commit）。
- 不改 backend、数据库、OpenAPI、store、SSE、生成流程、播放器业务逻辑或 ShareCard 输出。
- `GlobalMusicPlayer` 与内部 `MusicPlayer` 必须继续挂载在 RootLayout 持久边界，不能因路由或折叠状态卸载。
- `/play`、`/e2e-regression` 等尚未迁移页面维持现有顶部声音定位；仅 `/`、`/saves`、`/presets` 使用新的底部壳层预算，避免提前触碰 PR4 的 ChatBar 状态机。
- 保留存档用户隔离、401/AbortError 行为、上海时区显示、排序、继续/删除调用顺序；保留预设加载/删除调用顺序。

## 设计与接口

### AppShell

```ts
interface AppShellProps extends React.ComponentPropsWithoutRef<"div"> {
  fixedRegions?: React.ReactNode;
}
```

- RootLayout 结构为 `ErrorReporter -> AppShell(children + GlobalMusicPlayerWrapper)`。
- `data-slot="app-shell-content"` 只在存在 `data-app-shell-reserve="bottom"` 的真实固定区域时获得 bottom reserve；无声音上下文时不留空白。
- 壳层定义统一 canvas、最小视口、safe-area 和固定反馈偏移；不强行给叙事页增加公共导航。

### 管理页共享语法

- 首页、存档、预设显示小写 `story101`；“人生草稿本”只作中文说明。
- 单页最多一个主 Surface。列表是一个 reading surface 内的分隔行，不再是一组 Card。
- 管理页无书签或伪 editorial metadata。

### DestructiveConfirmDialog

```ts
interface DestructiveConfirmDialogProps {
  open: boolean;
  itemKind: "存档" | "角色预设";
  itemName: string;
  busy: boolean;
  error?: string | null;
  onOpenChange(open: boolean): void;
  onConfirm(): void;
}
```

- 明确显示目标名与“删除后无法恢复”。
- 取消按钮获得显式初始焦点；busy 时禁止关闭/重复提交，Dialog 标记 `aria-busy`，按钮文案为“正在删除”。
- 失败在弹窗内用 `FeedbackNotice tone="danger"` 呈现并保留重试；成功在页面级单一 status 呈现并带目标名。

## TDD 切片

### Task 1：AppShell 与声音固定区域

1. 先写 AppShell unit tests：RootLayout 持久边界、fixed region slot、无播放器时无 reserve、迁移路由 bottom reserve、legacy 路由 top placement、44px 控件、展开/跨路由不卸载。
2. 新增 `AppShell.tsx`、导出与最小 globals CSS；RootLayout 迁移并更新 metadata 为 `story101`。
3. GlobalMusicPlayer 仅调整外层布局/视觉 class 与 a11y，保持所有 selectors、store、effect、MusicPlayer 挂载语义不变。

### Task 2：首页与认证

1. 在 WelcomePage tests 先添加失败断言：`story101` 品牌、无旧 Story Life/AI tagline、真实 label/description/error 关联、单一反馈区域、44px 操作、busy、私钥警告和复制反馈。
2. 迁移首页为安静门户：单一 reading surface、主次动作行、无 gradient/glow/card 套卡。
3. 认证 Sheet 使用 FormField/Input/FeedbackNotice 与 overlay token；保留 register/login/fetchMe/logout/prefetch/复制/导航调用次数和参数。

### Task 3：存档与预设

1. 先补删除目标、默认焦点、busy、重复提交、弹窗内失败、成功 status、长中文、320px 语义测试。
2. 存档加载重试复用同一捕获路径，第二次失败仍为 error，不误落空态。
3. 预设新增显式 load error/retry；失败不伪装空态。
4. 两页迁移为单一 reading surface 分隔列表；主动作与危险区分离；所有图标动作有完整可访问名称且至少 44px。

### Task 4：真实页面 E2E 与验收

1. 新增确定性 Playwright，route mock `/auth/me`、`/games`、`/presets` 及 DELETE；不调用生成服务。
2. 覆盖首页未登录/认证 sheet、存档正常/空/失败/删除失败、预设正常/空/失败；验证真实页面而非组件墙。
3. 1440x900、390x844 截图；320/375/390 无横向溢出 smoke；文本字号、touch target、单一 raised surface、声音 reserve、弹窗焦点/busy/失败。
4. 聚焦 Jest、types、lint、目标 Playwright、production build，最后运行 `./scripts/test-run-isolated.sh --namespace story101_app_shell all`。

## 完成条件

- UI 和 metadata 不再显示 Story Life；UI 品牌为小写 story101。
- 首页/认证/存档/预设无 glow、卡片套卡、伪英文元数据或大面积状态色。
- 声音条在已迁移页面不遮挡最后一项内容、反馈或 safe-area；在 play/e2e legacy 页位置和 ChatBar 避让保持不变。
- 删除包含对象名、不可恢复说明、取消默认焦点、busy/失败可感知，且实际 DELETE 只发送一次。
- 所有既有业务回调参数、顺序、请求次数和恢复路径不变。
