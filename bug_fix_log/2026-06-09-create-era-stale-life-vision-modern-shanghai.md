# 创建页现代上海愿景生成北宋时代背景

日期：2026-06-09

## 问题

生产环境 `https://story101.live/create` 中，从首页进入新游戏后：

1. 输入角色名：`许知夏`
2. 输入人生愿景：`现代上海，独立游戏开发者，女性，关注叙事设计和音乐创作，不要古代、不要穿越。`
3. 第 1 步时代背景显示为：`1100年北宋中后期...科举制度完善...`

这是 P1 设定漂移。它发生在角色创建向导阶段，和故事生成阶段的现代设定漂移不是同一个入口。

## 根因

1. 前端创建向导只要角色名存在就会自动触发时代背景生成。用户常见输入顺序是先填姓名，再填人生愿景，因此第一次生成请求可能带着空愿景发出。
2. 旧请求返回后没有检查姓名/愿景是否已经变化，导致空愿景生成出的古代时代背景仍展示为可接受结果。
3. 后端已有现代愿景校正，但校正文案固定为互联网产品经理模板，没有保留“独立游戏开发者 / 叙事设计 / 音乐创作”的职业语义。

## 复现证据

- browser-agent 页面：`https://story101.live/create`
- DOM 状态显示：
  - 人生愿景包含“现代上海、独立游戏开发者、不要古代、不要穿越”
  - 时代背景内容包含“1100年北宋中后期”“科举制度完善”

## 回归测试

- `frontend/src/__tests__/hooks/useCharacterCreation.test.ts`
  - `discards era generated from stale life vision when user edits vision before response returns`
  - 覆盖旧生成请求返回前用户修改愿景时，旧时代背景不能进入 `generatedContent`。

- `tests/test_character_creation_deep.py`
  - `test_generate_era_honors_modern_shanghai_game_developer_life_vision`
  - 覆盖 AI 返回北宋时，现代上海游戏开发者愿景会被校正为现代数字内容/独立游戏行业。

## 修复

1. `useCharacterCreation` 增加基础信息版本号；姓名或愿景变化会立即让当前生成请求失效。
2. 生成响应返回时比较请求版本、当前步骤、姓名和愿景；过期响应直接丢弃。
3. 第 1 步基础信息变化后允许重新触发时代背景生成。
4. 后端现代时代校正新增游戏/叙事/音乐创作画像，避免固定落到产品经理模板。

## 验证

- `python -m pytest tests/test_character_creation_deep.py -q`：41 passed
- `npx jest src/__tests__/hooks/useCharacterCreation.test.ts --runInBand`：91 passed
- `./test.sh all`：Preflight + Layer 1-5 全部通过

## 状态

已本地修复并通过全量验证。提交、推送、部署后需要在生产创建页重新验证“现代上海独立游戏开发者”不再生成古代时代背景。
