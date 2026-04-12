---
name: test-friends
description: 好友系统功能回归测试
---

# 好友系统功能回归测试

## 前置条件
- 前端运行在 http://localhost:3000
- 后端运行在 http://localhost:8000
- 使用测试账号：FriendTestUser1 和 FriendTestUser2（需两个账号测试交互）

## 测试步骤

### TC-01: 好友页面入口
**操作**：使用 FriendTestUser1 登录，导航到 /profile 或好友入口页面。
**预期结果**：好友页面正常渲染，显示好友相关的UI元素（好友列表、搜索框等）。
**截图**：截图并记录好友页面完整布局。

### TC-02: 空好友列表
**操作**：使用新注册的 FriendTestUser1（无好友状态），查看好友列表。
**预期结果**：显示"暂无好友"或类似的空状态提示，无报错。
**截图**：截图记录空好友列表状态。

### TC-03: 发送好友请求
**操作**：在好友页面输入 FriendTestUser2 的 public_id，点击发送好友请求按钮。
**预期结果**：请求成功发出，显示"请求已发送"或类似的成功提示。
**截图**：截图记录发送请求后的提示信息。

### TC-04: 查看待处理请求
**操作**：切换到 FriendTestUser2 账号登录，进入好友页面查看待处理请求。
**预期结果**：显示来自 FriendTestUser1 的好友请求通知，包含接受/拒绝操作。
**截图**：截图记录待处理请求的显示内容。

### TC-05: 接受好友请求
**操作**：以 FriendTestUser2 身份点击接受好友请求。
**预期结果**：请求被接受，FriendTestUser1 出现在好友列表中，双方互为好友。
**截图**：截图记录接受后的好友列表。

### TC-06: 好友列表显示
**操作**：查看好友列表中的好友信息。
**预期结果**：好友信息正确显示，包含用户名、头像等基本信息，布局正常。
**截图**：截图记录好友列表的详细显示。

### TC-07: 删除好友
**操作**：点击好友旁的删除按钮，确认弹窗后执行删除。
**预期结果**：确认弹窗正常显示，确认后好友从列表中移除，列表即时更新。
**截图**：截图记录删除确认弹窗和删除后的列表状态。

### TC-08: 拒绝好友请求
**操作**：FriendTestUser1 再次向 FriendTestUser2 发送好友请求，FriendTestUser2 点击拒绝。
**预期结果**：请求被拒绝，双方不成为好友，请求从待处理列表中消失。
**截图**：截图记录拒绝操作和结果。

### TC-09: 重复请求处理
**操作**：向已经是好友的用户再次发送好友请求。
**预期结果**：系统给出适当提示（如"对方已是你的好友"），不发送重复请求。
**截图**：截图记录重复请求时的提示信息。

### TC-10: 未登录访问限制
**操作**：登出当前账号，直接访问好友页面 URL。
**预期结果**：页面跳转到登录页面或显示需要登录的提示，不暴露好友数据。
**截图**：截图记录未登录时的页面跳转或提示。

## 通过标准
- TC-01 ~ TC-10 全部通过
- 好友请求的发送、接受、拒绝流程完整无误
- 好友列表的增删操作即时生效
- 未登录状态下的访问控制正常
- 无 JS 错误或 API 报错

## 输出格式
```
测试时间: YYYY-MM-DD HH:MM
测试账号: FriendTestUser1, FriendTestUser2
前端版本: [commit hash]
后端版本: [commit hash]

| 用例   | 结果 | 截图路径                        | 备注 |
|--------|------|---------------------------------|------|
| TC-01  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-02  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-03  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-04  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-05  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-06  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-07  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-08  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-09  | PASS/FAIL | /path/to/screenshot.png    |      |
| TC-10  | PASS/FAIL | /path/to/screenshot.png    |      |

总结: X/10 通过
```
