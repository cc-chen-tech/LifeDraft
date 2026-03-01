# 前端测试覆盖率优化方案

## 当前状态

| 指标 | 当前覆盖率 | 目标覆盖率 |
|------|-----------|-----------|
| Statements | 57.76% | 75% |
| Branches | 49.43% | 65% |
| Functions | 57.9% | 70% |
| Lines | 59.07% | 75% |

---

## 阶段一：核心状态管理（优先级：P0）

### 1.1 stores/useGameStore.ts
**当前覆盖率：23.28% → 目标：60%**

#### 需要补充的测试点：

| 方法 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| `loadGameState()` | 正常加载、从round_history恢复、从last_round_full_story恢复 | 3 |
| `syncState()` | 正常同步、session 404自动恢复、游戏不存在清理状态 | 3 |
| `syncPlayerState()` | 正常同步、session过期重载、状态更新判断 | 3 |
| `generatePlayerImage()` | 正常生成、缺少gameId错误、缺少playerName错误 | 3 |
| `regeneratePlayerImage()` | 正常重新生成、无图片错误 | 2 |
| `regenerateFreshPlayerImage()` | 完全重新生成 | 2 |
| `generateSummary()` | 正常生成、失败处理 | 2 |
| `shallowChanged()` | 浅比较逻辑、keyFields过滤 | 2 |

**预估新增测试：20个用例**
**预期提升覆盖率：+8~10%**

---

## 阶段二：游戏核心逻辑（优先级：P0）

### 2.1 hooks/game/useEventGenerator.ts
**当前覆盖率：25.34% → 目标：60%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| `generateEvent()` | 正常生成、重复调用防护、错误处理、重试机制 | 4 |
| `prefetchNextEvent()` | 预生成成功、预生成失败、取消预生成 | 3 |
| SSE回调处理 | onStory、onComplete、onError、onStatus | 4 |
| 连接状态处理 | connecting、reconnecting、error | 3 |
| 清理逻辑 | abort清理、组件卸载清理 | 2 |

**预估新增测试：16个用例**
**预期提升覆盖率：+6~8%**

### 2.2 hooks/game/useGameState.ts
**当前覆盖率：29.70% → 目标：60%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| `handleSave()` | 保存成功、保存失败 | 2 |
| `handleContinueAfterSummary()` | 继续游戏、清空总结 | 2 |
| `handleContinueToNextRound()` | 进入下一轮、触发事件生成 | 2 |
| `handleAdjustStory()` | 调整故事、API错误 | 2 |
| `handleRegenerate()` | 重新生成、流式/非流式 | 2 |
| 状态流转 | loading→generating→options→result | 3 |

**预估新增测试：13个用例**
**预期提升覆盖率：+5~7%**

### 2.3 hooks/game/useChoiceHandler.ts
**当前覆盖率：17.02% → 目标：50%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| `handleChoice()` | 正常选择、SSE成功、SSE失败fallback | 3 |
| `handleCustomChoice()` | 自定义选择、验证输入 | 2 |
| 错误处理 | 网络错误、session过期、choice_already_processed | 3 |
| 流式处理 | onStory回调、onComplete回调 | 2 |

**预估新增测试：10个用例**
**预期提升覆盖率：+4~6%**

---

## 阶段三：页面组件（优先级：P1）

### 3.1 app/create/page.tsx
**当前覆盖率：30.06% → 目标：50%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| 步骤切换 | 下一步、上一步、步骤验证 | 3 |
| AI生成 | 设置生成、关系生成、属性生成 | 3 |
| 预设加载 | 加载预设、应用预设 | 2 |
| 图片生成 | 生成图片、重新生成 | 2 |
| 表单验证 | 必填项验证、提交创建 | 2 |

**预估新增测试：12个用例**
**预期提升覆盖率：+3~5%**

### 3.2 app/saves/page.tsx
**当前覆盖率：50.42% → 目标：70%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| 存档列表 | 加载列表、空列表 | 2 |
| 加载存档 | 正常加载、加载失败 | 2 |
| 删除存档 | 删除确认、删除成功 | 2 |
| 时间回溯 | 查看时间线、加载历史状态 | 2 |

**预估新增测试：8个用例**
**预期提升覆盖率：+2~4%**

---

## 阶段四：UI组件（优先级：P2）

### 4.1 components/game/StreamingText.tsx
**当前覆盖率：0% → 目标：60%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| 流式显示 | 正常流式、速度控制 | 2 |
| 完成回调 | onComplete触发 | 1 |
| 清理逻辑 | 组件卸载清理 | 1 |

**预估新增测试：4个用例**

### 4.2 components/game/SettingDisplay.tsx
**当前覆盖率：32.43% → 目标：60%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| 设置展示 | 不同类型设置展示 | 2 |
| 反馈功能 | 提交反馈、重新生成 | 2 |
| 加载状态 | skeleton展示 | 1 |

**预估新增测试：5个用例**

---

## 阶段五：工具函数完善（优先级：P1）

### 5.1 lib/remote-log.ts
**当前覆盖率：13.33% → 目标：60%**

#### 需要补充的测试点：

| 功能 | 测试场景 | 预估用例数 |
|------|---------|-----------|
| `remoteLog()` | 正常发送、失败处理、不同级别 | 3 |
| 队列管理 | 队列满、网络恢复后发送 | 2 |
| 错误处理 | 发送失败不阻塞业务 | 1 |

**预估新增测试：6个用例**
**预期提升覆盖率：+1~2%**

---

## 实施计划

### 第一阶段（预计 2-3 天）
**目标：覆盖率提升至 65%**

- [ ] stores/useGameStore.ts 核心方法测试
- [ ] hooks/game/useEventGenerator.ts 基础测试
- [ ] hooks/game/useGameState.ts 基础测试

**预估新增：49个测试用例**

### 第二阶段（预计 2-3 天）
**目标：覆盖率提升至 72%**

- [ ] hooks/game/useChoiceHandler.ts 完整测试
- [ ] app/create/page.tsx 核心流程测试
- [ ] app/saves/page.tsx 基础测试

**预估新增：30个测试用例**

### 第三阶段（预计 1-2 天）
**目标：覆盖率提升至 75%**

- [ ] components/game/ 关键组件测试
- [ ] lib/remote-log.ts 测试
- [ ] 补充边界条件测试

**预估新增：15个测试用例**

---

## 测试策略

### 1. Mock策略
```typescript
// API Mock
jest.mock('@/lib/api', () => ({
  default: {
    games: { load: jest.fn(), save: jest.fn() },
    gameplay: { getState: jest.fn(), generateEventSync: jest.fn() },
    images: { generate: jest.fn(), regenerate: jest.fn() },
  }
}));

// SSE Mock
jest.mock('@/lib/sse', () => ({
  streamGameEvent: jest.fn(),
  streamChoice: jest.fn(),
}));

// Store Mock
jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(),
    setState: jest.fn(),
  }
}));
```

### 2. 测试结构
```typescript
describe('useGameStore', () => {
  describe('loadGameState', () => {
    it('正常加载游戏状态');
    it('从round_history恢复故事');
    it('处理加载错误');
  });
  
  describe('syncState', () => {
    it('正常同步状态');
    it('session 404时自动恢复');
    it('游戏不存在时清理状态');
  });
});
```

### 3. 关键验证点
- 状态变化是否符合预期
- API调用参数是否正确
- 错误处理是否完善
- 边界条件是否覆盖

---

## 风险与注意事项

1. **usePlayGame.ts 测试困难**：该 hook 过于复杂，建议拆分为更小的 hooks 再测试
2. **SSE测试环境**：需要完善的 mock 机制
3. **Zustand persist**：测试时需要处理 localStorage mock
4. **图片生成**：涉及异步和文件处理，测试较复杂

---

## 验收标准

- [ ] Statements 覆盖率 ≥ 75%
- [ ] Branches 覆盖率 ≥ 65%
- [ ] Functions 覆盖率 ≥ 70%
- [ ] Lines 覆盖率 ≥ 75%
- [ ] 所有 P0 模块覆盖率 ≥ 60%
- [ ] 测试通过率 100%
- [ ] 无 console.error 警告

---

*方案制定时间：2026-02-24*
*当前覆盖率基准：57.76% (Statements)*
