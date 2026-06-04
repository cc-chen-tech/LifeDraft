# 2026-06-03 Collection Key Characters Recognition

## 问题

第4周长历史中，智能识别只剩主角或空人物候选。故事正文已经出现陈一鸣、陈律师、张副总、赵铭、刘洋、周先生、王亮等关键人物，但这些人物没有稳定进入 collection 候选。

## 原因

- `src/api/routers/collection.py` 的 `_build_eligible_recognition_characters` 只读取 `character_settings.relationships.key_people`、`important_people` 和 `family_members`，没有读取 `player_state.relationships`、历史/当前事件 effects 中的关系人物，以及 `pending_storylines`、`character_habits` 等明确人物元数据。
- `src/services/entity_recognition_service.py` 的中文人名兜底规则偏古代叙事，缺少 `刘` 姓、现代职位称谓（如律师、副总）和现代动作触发词（如提出、承认、否认、递来、打来），导致 AI 空结果时无法补足关键人物。

## 修复

- 扩展 collection recognition eligibility：兼容 dict/list 角色设定结构，补充关系分数字典、历史/当前事件 relationship effects、剧情线相关人物、伏笔相关人物、人物习惯、角色弧光和世界呼吸事件中的明确 NPC。
- 扩展实体识别兜底：补入 `刘` 姓、现代职位称谓和现代动作触发词。
- 保持 metadata gating：公司、地点、物品不会因为只在故事文本中出现而成为人物候选。

## 测试

- 新增路由 helper 回归：当前事件关系和剧情角色元数据中的关键人物进入 eligibility，主角和公司名不进入。
- 新增服务回归：第4周长历史中 `陈一鸣`、`陈律师`、`张副总`、`赵铭`、`刘洋`、`周先生`、`王亮` 都能在 AI 空结果下进入人物候选，同时 `启明集团`、`银行会议室`、`合同`、`公章` 等不被误判为人物。

## 验证命令

```bash
pytest tests/test_collection_recognition_current_event.py::test_recognition_eligibility_includes_current_event_relationships_and_story_roles tests/test_entity_recognition_async.py::TestMinAppearancesBoundary::test_long_history_modern_key_characters_with_roles_reach_candidates -q
pytest tests/test_collection_recognition_current_event.py tests/test_entity_recognition_async.py tests/test_live_gameplay_recovery_collection_contract.py -q
```

结果：目标测试集 46 passed。
