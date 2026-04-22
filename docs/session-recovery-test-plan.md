# Session 恢复机制测试方案

> 最后更新：2026-04-19  
> 状态：部分内容为历史修复记录，已按当前代码结构修正路径说明。

## 修复背景

当用户点击"确认并继续"后，如果后端 session 过期或重启，前端会恢复 session。此前的实现可能会恢复旧的 `currentEvent`，导致：
- 前端显示旧选项
- 后端没有对应的 `current_event`
- 用户点击选项时报错 "No current event"

## 修复内容

### 前端修复

| 修复点 | 文件 | 说明 |
|--------|------|------|
| 新增 `syncPlayerState` | `frontend/src/stores/useGameStore.ts` | 只同步玩家状态，不恢复 currentEvent |
| 修改 `handleContinueToNextRound` | `frontend/src/hooks/usePlayGame.ts` | 使用 syncPlayerState 代替 syncState |
| 修改 `handleContinueAfterSummary` | `frontend/src/hooks/usePlayGame.ts` | 使用 syncPlayerState 代替 syncState |
| 修改 `generateEvent` onError | `frontend/src/hooks/usePlayGame.ts` | session 恢复后重新生成，不使用旧选项 |
| **选择成功后清空 currentEvent** | `frontend/src/hooks/usePlayGame.ts` | 避免刷新页面时从 localStorage 恢复旧选项 |
| **不再持久化 currentEvent** | `frontend/src/stores/useGameStore.ts` | 从 partialize 中移除 currentEvent |
| **选择失败时自动重新生成** | `frontend/src/hooks/usePlayGame.ts` | 遇到 "No current event" 错误时重新生成事件 |
| 新增调试端点 | `src/api/routers/gameplay/summary.py` | `DELETE /api/games/{game_id}/session-debug` |

### 后端修复

| 修复点 | 文件 | 说明 |
|--------|------|------|
| **自动从数据库恢复 session** | `src/api/services/session_service.py` + gameplay 路由 | `get_or_restore()` 在内存缺失时从数据库恢复 |

### 核心改进：Session 自动恢复

**之前**：
```
后端重启 → session 丢失 → 返回 404 → 前端处理恢复
```

**现在**：
```
后端重启 → session 丢失 → 自动从数据库恢复 → 继续处理请求
```

用户体验：后端重启后，用户操作无感知，自动恢复并继续。

## 测试场景

| # | 场景 | 触发条件 | 预期结果 |
|---|------|---------|---------|
| 1 | 正常流程 | 选择→确认并继续 | 生成新事件，不显示旧选项 |
| 2 | 继续时 session 过期 | 点击确认并继续前清空 session | 恢复 session + 生成新事件 |
| 3 | 生成中 session 过期 | 事件生成 SSE 过程中清空 session | 恢复 session + 重新生成 |
| 4 | 选择时 session 过期 | 显示选项后、点击前清空 session | 恢复 session + 重试选择 |

## 测试步骤

### 准备工作

```bash
# 启动服务
cd /Users/luicy/AI/story2
./start.sh

# 打开浏览器访问
open http://localhost:3000
```

### 获取 game_id

在浏览器 Console 中执行：

```javascript
JSON.parse(localStorage.getItem('game-storage')).state.gameId
```

### 清空 session（模拟过期）

```bash
# 替换 {game_id} 为实际值
curl -X DELETE "http://localhost:8000/api/games/{game_id}/session-debug"
```

## 详细测试步骤

### 场景 1：正常流程

1. 开始游戏，进入 play 页面
2. 等待事件生成完成，显示选项
3. 选择一个选项
4. 看到结果后，点击"确认并继续"
5. **验证**：生成新事件，不会显示旧选项

### 场景 2：继续时 session 过期

1. 开始游戏，进入 play 页面
2. 等待事件生成完成，显示选项
3. 选择一个选项，看到结果
4. **在点击"确认并继续"前**，执行：
   ```bash
   curl -X DELETE "http://localhost:8000/api/games/{game_id}/session-debug"
   ```
5. 点击"确认并继续"
6. **验证**：
   - 前端 Console 有 `[syncPlayerState] Session expired` 日志
   - 自动恢复 session 并生成新事件
   - 不会显示旧选项

### 场景 3：生成中 session 过期

1. 开始游戏，选择选项后点击"确认并继续"
2. **在事件生成过程中**（loading 状态），快速执行：
   ```bash
   curl -X DELETE "http://localhost:8000/api/games/{game_id}/session-debug"
   ```
3. **验证**：
   - 前端 Console 有 `[generateEvent] Session expired, restoring and regenerating` 日志
   - 自动恢复 session 并重新生成事件

### 场景 4：选择时 session 过期

1. 开始游戏，等待事件生成完成
2. **在显示选项后、点击选项前**，执行：
   ```bash
   curl -X DELETE "http://localhost:8000/api/games/{game_id}/session-debug"
   ```
3. 点击选择一个选项
4. **验证**：
   - 后端尝试从数据库恢复 current_event
   - 如果恢复成功，选择完成
   - 如果恢复失败，显示错误提示

## 验证清单

- [ ] 场景 1：正常流程能正常生成新事件
- [ ] 场景 2：继续时 session 过期能自动恢复并生成新事件
- [ ] 场景 3：生成中 session 过期能自动恢复并重新生成
- [ ] 场景 4：选择时 session 过期能正确处理
- [ ] 所有场景不会显示旧选项（重复选项问题）
- [ ] 前端 Console 有相应的日志输出
- [ ] 用户流程不中断，最终能正常继续游戏

## 相关日志关键词

前端 Console 日志：
- `[syncPlayerState]` - 同步玩家状态
- `[generateEvent]` - 事件生成
- `[handleContinueToNextRound]` - 继续下一轮

后端日志：
- `[DEBUG] Cleared session` - session 被清空
- `Session expired` - session 过期
- `Restored current event from database` - 从数据库恢复事件

## 清理调试端点

测试完成后，可以考虑移除调试端点：
- 文件：`src/api/routers/gameplay/summary.py`
- 搜索：`session-debug`
