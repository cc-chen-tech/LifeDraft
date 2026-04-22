# 分支保护规则配置指南

> 最后更新：2026-04-19

本文档说明如何在 GitHub 上配置分支保护规则，以确保代码质量和团队协作规范。

## 概述

### 什么是分支保护

分支保护（Branch Protection）是 GitHub 提供的一项功能，允许仓库管理员对特定分支设置规则和限制，防止未经审核的代码直接推送到重要分支（如 `main`）。

### 为什么要使用分支保护

1. **防止意外推送**：避免未经测试的代码直接进入主分支
2. **强制代码审查**：确保所有变更都经过至少一名其他开发者审核
3. **自动化检查**：集成 CI/CD 工作流，确保测试通过后才能合并
4. **团队协作规范**：建立统一的代码合并流程
5. **追溯性**：所有变更都通过 Pull Request 进行，便于追踪和回滚

## 前置条件

在配置分支保护规则之前，请确保满足以下条件：

### 1. GitHub Actions 工作流已配置

以下工作流文件应已存在于 `.github/workflows/` 目录中：

| 工作流文件 | 说明 | 来源 |
|-----------|------|------|
| `backend-tests.yml` | 后端单元测试 | 单元4 |
| `frontend-tests.yml` | 前端单元测试 | 单元5 |
| `frontend-lint.yml` | 前端代码规范检查 | 单元6 |
| `e2e-tests.yml` | 端到端测试 | 单元7 |
| `python-quality.yml` | Python 代码质量检查 | 单元8 |
| `wiki-check.yml` | Wiki 完整性检查 | 文档治理 |

> **注意**：如果某些工作流尚未创建，请先完成对应单元的配置，或在分支保护中暂时跳过这些检查。

### 2. 管理员权限

你需要拥有仓库的 **Admin（管理员）** 权限才能配置分支保护规则。

## 配置步骤

### 步骤 1：进入分支设置页面

1. 打开 GitHub 仓库页面
2. 点击顶部导航栏的 **Settings**（设置）标签
3. 在左侧侧边栏中，点击 **Branches**（分支）选项

```
[截图位置：Settings 页面侧边栏，Branches 选项高亮]
```

### 步骤 2：添加分支保护规则

1. 在 "Branch protection rules" 区域，点击 **Add rule**（添加规则）按钮

```
[截图位置：Add rule 按钮]
```

### 步骤 3：配置分支名称模式

1. 在 "Branch name pattern" 输入框中，输入要保护的分支名称：
   ```
   main
   ```

2. 如果你需要保护多个分支，可以使用通配符模式：
   - `main` - 仅保护 main 分支
   - `release/*` - 保护所有以 release/ 开头的分支
   - `*` - 保护所有分支

```
[截图位置：Branch name pattern 输入框，内容为 main]
```

### 步骤 4：启用保护规则选项

#### 4.1 要求 Pull Request 审核

勾选以下选项：

- [x] **Require a pull request before merging**
  - [x] **Require approvals**（建议设置为 1）
  - [ ] Dismiss stale PR approvals when new commits are pushed（可选）
  - [ ] Require review from Code Owners（可选，如有 CODEOWNERS 文件可启用）

```
[截图位置：Pull Request 审核选项区域，显示已勾选状态]
```

#### 4.2 要求状态检查通过

勾选以下选项：

- [x] **Require status checks to pass before merging**
  - [x] **Require branches to be up to date before merging**（建议勾选）

在 "Search for status checks in the last week for this repository" 搜索框中，添加以下工作流：

| 状态检查名称 | 说明 |
|-------------|------|
| `backend-tests` | 后端单元测试（来自单元4） |
| `frontend-tests` | 前端单元测试（来自单元5） |
| `frontend-lint` | 前端代码规范检查（来自单元6） |
| `e2e-tests` | 端到端测试（来自单元7） |
| `python-quality` | Python 代码质量检查（来自单元8） |
| `wiki-check` | Wiki 完整性检查（文档治理） |

添加方法：
1. 在搜索框中输入工作流名称
2. 从下拉列表中选择对应的工作流
3. 重复上述步骤添加所有需要的工作流

```
[截图位置：Status checks 区域，显示已添加的工作流列表]
```

#### 4.3 其他推荐选项

- [x] **Include administrators**（推荐勾选）
  - 确保管理员也遵守相同的规则，防止意外操作

- [ ] **Restrict pushes that create files larger than 100 MB**
  - 防止大文件被意外提交

- [ ] **Require linear history**（可选）
  - 强制线性提交历史，禁止合并提交

- [ ] **Require signed commits**（可选）
  - 要求所有提交都必须经过 GPG 签名

- [ ] **Require conversation resolution before merging**（可选）
  - 要求所有 PR 评论都被解决后才能合并

### 步骤 5：保存规则

1. 确认所有配置选项正确无误
2. 点击页面底部的 **Create** 或 **Save changes** 按钮

```
[截图位置：Create/Save changes 按钮]
```

## 验证配置

### 验证方法 1：创建测试 Pull Request

1. 创建一个新分支：
   ```bash
   git checkout -b test-branch-protection
   ```

2. 做一些任意修改并提交：
   ```bash
   echo "# test" >> README.md
   git add README.md
   git commit -m "test: branch protection"
   git push origin test-branch-protection
   ```

3. 在 GitHub 上创建 Pull Request

4. 观察以下行为：
   - [ ] 直接推送到 `main` 分支应该被拒绝
   - [ ] PR 页面显示需要的状态检查
   - [ ] 在检查通过前，"Merge" 按钮应为灰色/不可用
   - [ ] 需要至少 1 个审核批准才能合并

### 验证方法 2：检查保护规则列表

1. 返回 Settings > Branches 页面
2. 确认 `main` 分支显示在保护规则列表中
3. 点击规则名称，确认所有配置正确

```
[截图位置：Branch protection rules 列表，显示 main 规则]
```

### 验证方法 3：检查状态检查运行

1. 在任意 PR 页面，查看 "Checks" 标签
2. 确认所有配置的工作流都在运行
3. 确认工作流名称与分支保护中配置的一致

```
[截图位置：PR 页面的 Checks 标签，显示所有检查状态]
```

## 故障排除

### 问题 1：状态检查未显示在列表中

**现象**：在搜索状态检查时，找不到某个工作流

**原因**：
- 该工作流最近7天内没有在仓库中运行过
- 工作流文件配置错误

**解决方法**：
1. 手动触发该工作流一次：
   - 进入 Actions 页面
   - 选择对应工作流
   - 点击 "Run workflow" 手动运行
2. 检查工作流文件语法是否正确
3. 确保工作流文件位于 `.github/workflows/` 目录

### 问题 2：管理员可以直接推送

**现象**：管理员能够绕过保护规则直接推送到 main

**原因**：未勾选 "Include administrators" 选项

**解决方法**：
1. 编辑分支保护规则
2. 勾选 "Include administrators"
3. 保存更改

### 问题 3：PR 合并按钮始终可用

**现象**：即使检查未通过，合并按钮仍然可以点击

**原因**：
- 可能勾选了 "Require status checks" 但没有选择具体检查项
- 或者某些检查项被标记为 "Required" 但实际未运行

**解决方法**：
1. 编辑分支保护规则
2. 确保在 "Status checks that are required" 列表中添加了具体的工作流
3. 确保工作流名称拼写完全正确（区分大小写）

### 问题 4：工作流名称不匹配

**现象**：配置的保护规则中工作流名称与实际运行的工作流名称不一致

**解决方法**：
1. 查看最近的 PR 或 Actions 运行记录
2. 确认工作流的实际显示名称（Job 名称）
3. 更新分支保护规则中的名称

例如，如果工作流文件如下：
```yaml
name: Backend Tests
jobs:
  test:
    name: backend-tests  # 这是实际显示的名称
```

则在分支保护中应该搜索 `backend-tests` 而不是 `Backend Tests`。

### 问题 5：紧急情况下需要绕过保护规则

**场景**：生产环境出现紧急问题，需要快速修复

**临时解决方法**（仅限仓库管理员）：

1. **临时禁用保护规则**（不推荐）：
   - Settings > Branches
   - 删除或编辑 main 分支的保护规则
   - 完成紧急修复后重新启用

2. **使用管理员权限强制合并**（较安全）：
   - 在 PR 页面，管理员可以看到 "Merge without waiting for requirements to be met" 选项
   - 仅在真正紧急的情况下使用

3. **预先配置例外规则**（推荐）：
   - 可以创建一个 `hotfix/*` 分支模式，设置较少的限制
   - 紧急修复在 hotfix 分支上进行，通过 PR 合并到 main

## 最佳实践

1. **始终启用 "Include administrators"**
   - 防止任何人（包括自己）意外直接推送代码

2. **合理设置审核人数**
   - 小型团队：1人审核即可
   - 中大型团队：核心模块建议2人审核

3. **保持工作流稳定**
   - 不要将不稳定或经常失败的测试加入必需检查
   - 确保所有必需检查都能在合理时间内完成（建议 < 10分钟）

4. **定期审查保护规则**
   - 随着项目发展，可能需要调整保护规则
   - 建议每季度审查一次

5. **文档化例外流程**
   - 明确说明什么情况下可以绕过保护规则
   - 记录所有例外操作以便审计

## 参考链接

- [GitHub 官方文档 - 管理分支保护规则](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
- [GitHub 官方文档 - 关于状态检查](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks)
- [GitHub 官方文档 - 代码审查](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)
