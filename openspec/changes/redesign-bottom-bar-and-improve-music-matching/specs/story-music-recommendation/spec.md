## MODIFIED Requirements

### Requirement: Story analysis uses full text
音乐服务 MUST 使用完整 story_text 做 AI 分析，MUST NOT 在 service 层截断文本。

#### Scenario: Full text is passed to AI analysis
- **WHEN** `analyze_story_for_music()` 被调用
- **THEN** 完整的 `story_text` 被传给 AI 分析函数
- **AND** 不在 service 层做字符截断（AI client 层的 token 限制除外）

#### Scenario: Short story still works
- **WHEN** story_text 长度 < 500 字符
- **THEN** 分析正常工作，不因文本过短而失败

### Requirement: Multi-dimensional search query construction
搜索关键词构造 MUST 结合 mood、era、scene type、pacing、energy、instruments 多维度。

#### Scenario: Query combines multiple dimensions
- **WHEN** MusicBrief 包含 mood="紧张", scene_type="夜袭", instruments=["鼓","笛子"]
- **THEN** 搜索词列表 MUST 包含 "紧张 夜袭"、"古风 鼓" 等组合查询
- **AND** 不只用单一 mood 词搜索

#### Scenario: Negative cues excluded
- **WHEN** MusicBrief 包含 negative_cues=["流行人声"]
- **THEN** 搜索词 MUST NOT 包含被 negative cue 排除的词汇

### Requirement: Search result relevance ranking
Netease 搜索结果 MUST 按与 MusicBrief 的匹配度排序。

#### Scenario: Better match ranks higher
- **WHEN** 搜索返回多首歌曲
- **THEN** 歌名/专辑/艺人匹配 brief mood 或 scene 关键词的排在前面
- **AND** 完全无关的结果排在末尾或被过滤

#### Scenario: No results still degrades gracefully
- **WHEN** 所有搜索结果相关性都很低
- **THEN** 保留原有顺序作为 fallback
- **AND** 不抛出错误

### Requirement: AI generated tracks respect queue order
AI 生成曲目 MUST 仅插入后续队列位置，MUST NOT 切换当前播放歌曲。

#### Scenario: Generated track enters queue
- **WHEN** AI 音乐生成完成
- **THEN** 曲目被插入到 queue 的 index 1 或之后
- **AND** currentSong 保持不变

#### Scenario: No interruption of playback
- **WHEN** 当前有歌曲在播放且 AI 生成完成
- **THEN** 播放不中断、不切换
