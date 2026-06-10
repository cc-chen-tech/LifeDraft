# 角色时代设定反馈与时代倾向一致性修复（2026-06-10）

## 问题现象（复现）

- 在角色设置里，用户提交明确的现代化人生愿景（如“2020年代中国互联网公司，成为AI协作工具产品经理”）后，
  对“时代”点击“重新生成/反馈”。
- AI 会返回古代时代内容（例如“唐代…科举…”），并且因为反馈分支被绕过，后端直接返回古代设置，导致人物设定与愿景失配。
- 在另一个方向上，用户明确要求“避免现代科技/赛博朋克/公司化语境”等古典取向时，
  也可能被现代化的 `modern_profile` 覆盖，生成内容里仍出现“互联网、AI、公司”等现代线索。

## 根因

- `src/game/character_creation.py` 中 `_align_era_setting_with_life_vision` 存在早退逻辑：
  - 只要 `feedback` 非空就直接 `return era_setting`。
  - 这等于在反馈重生成路径关闭了现代愿景的时代纠偏。
- `新时代与古典约束` 还缺乏反向兜底：当用户显式反现代时，仍会被默认现代模板覆盖或混入。

## 修复

- 文件：`src/game/character_creation.py`
- 修改点：
  - `feedback` 参数仍可接收，但不再作为跳过时代纠偏的条件，反馈重生成路径也会执行一致性对齐。
  - 补充古典反向意图识别（`ANTI_MODERN_LIFE_VISION_CUES`）：
    - “古典 / 传统 / 古风 / 医者 / 师承 / 乡土 / 乡里 / 村落 / 不想现代 / 避免现代 / 避开现代 / 不要现代”。
  - `_align_era_setting_with_life_vision` 改为双向对齐：
    - 检测现代愿景时重写为现代风格；
    - 检测古典反向意图时重写为古代风格；
    - 两者都将打上 `_aligned_to_life_vision=True` 用于排障追踪。

## 新增测试（先写后改）

- 文件：`tests/test_character_creation_deep.py`
- 用例：`test_generate_era_feedback_still_aligns_with_modern_life_vision`
  - 输入古代 AI 结果 + 现代愿景 + feedback。
  - 断言：
    - `year >= 2020`
    - 返回描述不再出现古代关键词（唐、科举、古代）。
    - 返回文本包含现代线索（如“互联网”）。
    - `_aligned_to_life_vision` 为 `True`。
- 新增用例：`test_generate_era_prefers_historical_context_when_life_vision_forbids_modern`
  - 输入现代 AI 结果 + 反现代愿景文本。
  - 断言：
    - `year < 1900`
    - 返回描述不出现“互联网 / AI / 公司 / 现代”。
    - 仍命中“古代/古典”语义。
    - `_aligned_to_life_vision=True`。

## test.sh 覆盖

- `test.sh preflight` 增加该回归用例：
  - `tests/test_character_creation_deep.py::TestCharacterCreatorGenerateSetting::test_generate_era_feedback_still_aligns_with_modern_life_vision`
- `test.sh preflight` 已保持该新增测试在回归层固定执行，避免回归漏检。

## 验证结果

- `./test.sh preflight`：`119 passed`
- `./test.sh mypy`：通过（11 source files）
- `./test.sh imports`：`47 passed`
- `./test.sh contract`：`133 passed`
- `./test.sh db`：`96 passed`
- `./test.sh all`：全部通过（Preflight + mypy + imports + contract + db + e2e，共通过 303/303 前端测试与全量 96/96 DB测试）

## 影响范围与回归风险

- 修复专注“时代生成”与“用户时代意图”闭环，不影响 wealth/age 等其他 setting 逻辑与角色关系生成。
- 双向对齐后可能改变部分边缘提示词极短句（如仅含“古典”）下的既有输出；该范围在回归测试中已覆盖并归一化。
