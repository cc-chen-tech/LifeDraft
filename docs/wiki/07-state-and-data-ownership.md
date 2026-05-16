# 07 - State And Data Ownership

> 最后核对：2026-04-26

## 状态归属一览

- 前端临时 UI 状态：Zustand stores（`frontend/src/stores/*`）
- 服务端会话状态：`session_store` 中的 `GameLoopSession`
- 业务真实状态：`GameLoop.player_state`（内存）+ `GameState.state_json`（持久化）

## 一次回合中的状态流

1. 前端请求生成事件（SSE）。  
2. 后端 `GameLoop` 产出 `current_event`，并写入 `player_state.current_event_data`。  
3. 用户提交选择后，故事续写、属性变化、历史记录更新。  
4. 状态通过 `save_game_progress` 持久化到 `game_states`。  
5. 若会话丢失，`session_service` 从 DB 重建 `GameLoop`。

## 数据表职责（核心）

- `games`：会话主记录（用户归属、语言、结束态、约束级别、叙事风格 `narrative_style_id`）
- `game_states`：状态快照（支持普通进度与手动存档点）
- `decisions`：关键选择记录（检索与摘要，含决策历史扩展）
- `images` / `scene_images`：角色/物品/场景图片资产（时代一致性约束）
- `users` / `friendships`：账号与社交关系
- `game_playlists`：游戏剧情音乐播放列表（GamePlaylist）
- `achievements` / `life_reviews`：成就记录与人生回顾

## 升级时的 ownership 规则

1. 改前端 store 字段时，确认是否只是 UI 字段，还是会回写后端状态。  
2. 改 `PlayerState` 结构时，必须考虑旧 `state_json` 反序列化兼容。  
3. 改 `current_event` 生命周期时，必须覆盖”断线恢复 + 重连 replay + choice 幂等”场景。  
4. 改图片生成流程时，确认 `scene_images` 查询键（`game_id + week + round + stage`）不被破坏。
5. 改 `Game.narrative_style_id` 时，必须保证旧存档的默认回退逻辑。
6. 改 4D 资源（energy / mood / knowledge / wealth）时，前后端显示与消耗逻辑同步更新。

## 最容易引发回归的问题

- 内存状态已更新，但未持久化，导致刷新后丢失。  
- 持久化结构更新后，历史存档读取失败。  
- 前端误用旧接口路径，导致后端 404 或行为不一致。  
- SSE 完成事件格式改动后，前端解析器未同步更新。
