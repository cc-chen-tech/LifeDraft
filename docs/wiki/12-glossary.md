# 12 - Glossary

> 最后核对：2026-04-19

- `GameLoop`：游戏主循环对象，驱动事件生成、选择处理与进度推进。  
- `PlayerState`：玩家状态实体，包含资源、历史、角色设定、世界状态等。  
- `current_event`：当前轮正在展示/等待选择的事件。  
- `round_history`：按轮记录的故事与选择历史。  
- `SSE`：Server-Sent Events，用于流式返回故事文本和状态。  
- `Last-Event-ID`：SSE 断线重连时的游标，服务端据此回放缓存。  
- `SessionStore`：服务端内存会话仓库，管理 `GameLoopSession`。  
- `Session Restore`：会话缺失时从数据库状态重建 `GameLoop`。  
- `Constraint Harness`：叙事约束验证与重试控制系统。  
- `Narrative Style Engine`：基于风格模板生成叙事约束与提示。  
- `Creative Enhancement`：创意增强系统（情绪弧线、新颖性、伏笔等）。  
- `Epic Narrative`：史诗叙事系统（角色弧线、世界演进、冲突塔）。  
- `Feature Flag`：功能开关，用于灰度发布与风险隔离。  
- `Contract Test`：验证生产者/消费者字段与路径契约一致性的测试。  
- `Save Point`：手动存档点，用于时间回溯。
