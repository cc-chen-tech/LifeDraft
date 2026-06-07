# E2E next start standalone 环境修复记录

## 问题
E2E 生产模式前端使用 `next start`，但 `frontend/next.config.ts` 默认启用 `output: 'standalone'`。仅在 `next build` 时设置 `NEXT_DISABLE_STANDALONE=1` 后，`next start` 运行时仍会重新读取配置并打印：

`next start does not work with output: standalone configuration`

这会让本地/CI E2E 运行混入错误启动模式，增加前端启动不稳定风险。

## 复现
1. 运行 `NEXT_DISABLE_STANDALONE=1 npm run build`。
2. 再运行 `CI=1 E2E_FRONTEND_PORT=3000 npm run start -- --hostname 127.0.0.1 --port 3000`。
3. 仍能看到 standalone 相关警告。

## 修复
1. `frontend/next.config.ts` 保持生产默认 standalone，但在 `NEXT_DISABLE_STANDALONE=1` 时临时关闭输出模式。
2. `test.sh e2e` 在 build 和 start 两个阶段都传入 `NEXT_DISABLE_STANDALONE=1`。
3. `tests/test_gate_preflight_no_mock.py` 增加断言，保证 build/start 两处都带该环境变量。

## 验证
- 先运行新增 preflight 单测确认旧实现失败。
- 修改 `test.sh` 后重跑：
  - `python -m pytest tests/test_gate_preflight_no_mock.py::test_e2e_prod_frontend_disables_standalone_output_for_next_start -q`
- 结果通过。
