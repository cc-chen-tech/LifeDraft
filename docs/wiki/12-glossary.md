# 12 - Glossary

> 最后核对：2026-04-26

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
- `4D Resources`：四维资源系统（energy 精力 / mood 心情 / knowledge 学识 / wealth 财富）。
- `Era Validator`：时代一致性验证器，检测文本中的时代错位元素（如古风场景出现"手机"）。
- `AchievementEngine`：成就计算引擎，在结局时评估玩家表现并生成成就徽章。
- `LifeReview`：人生回顾生成器，在游戏结局时汇总玩家整局经历。
- `GamePlaylist`：游戏剧情音乐播放列表，关联游戏与推荐歌曲缓存。
- `CachedMusicPool`：音乐混合缓存池，缓存音乐分析与 URL 减少重复调用。
- `Narrative Style`：叙事风格（如 magical_realism、modern_urban 等），独立于系统开关控制文本风格。默认回退风格为 `magical_realism`（Bug #12 修复）。
- `SettingFeedbackCard`：角色创建 AI 反馈卡片，支持按维度（家庭/关系/特质/财富/肖像）反馈并再生设定。
