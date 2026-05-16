# Tasks: Test Architecture Improvement

## Workstream 1: SSE Mock → createSSEMock Utility

- [ ] 1.1 在 `src/__tests__/helpers/` 创建 `sse-mock.ts`，实现 `createSSEMock(chunks: string[])` 工具函数，返回带假 `getReader()` 的 Response
- [ ] 1.2 验证 `createSSEMock` 能驱动 `parseSSEStream` 真实运行
- [ ] 1.3 将 9 个 SSE mock 文件逐个迁移到 `createSSEMock` + `global.fetch`
- [ ] 1.4 删除所有 `jest.mock('@/lib/sse')`

## Workstream 2: Test Pyramid — Contract Alignment

- [ ] 2.1 识别前端 mock 数据中最关键的 5 个 API 端点
- [ ] 2.2 为每个端点写 Python 合同测试，锁定响应 JSON 的字段名和类型
- [ ] 2.3 前端 mock 数据对照合同测试校正字段名
- [ ] 2.4 为 3 个关键路径的 hook 加"不 replace store 方法"的集成测试

## Workstream 3: replaceMethods → spyOnStore Helper

- [ ] 3.1 在 `src/__tests__/helpers/` 创建 `store-spy.ts`，实现类型安全的 `spyOnStore` 工具
- [ ] 3.2 将类别 1 文件（~10 个纯直通 hook）改为直接断言 store 状态，删除 replaceMethods
- [ ] 3.3 将类别 2 文件（~10 个复杂逻辑）替换为 `spyOnStore` + 补充状态断言
- [ ] 3.4 将类别 3 文件（~5 个页面组件）替换为 `spyOnStore`
- [ ] 3.5 全量跑 805 个测试，确保零回归
