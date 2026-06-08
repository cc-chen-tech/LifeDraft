# E2E 后端缺少 JWT_SECRET

- 日期：2026-06-07
- 影响：在干净 worktree 或没有 `.env` 的环境中运行 `./test.sh e2e` 时，E2E 后端启动成功但 `/api/auth/register` 返回 500，导致大量浏览器用例在登录/注册前置步骤级联失败。

## 复现

运行：

```bash
./test.sh e2e
```

修复前结果：核心 E2E 在 10 个失败后提前停止，主要错误为 `Registration failed: 500`。`/tmp/backend_e2e.log` 中对应异常为 `JWT_SECRET environment variable is required`。

## 原因

生产代码要求 `JWT_SECRET` 必须由环境变量提供，不能使用硬编码默认值。但 `test.sh` 的 E2E 后端启动命令只设置了 E2E host/port、MiniMax 测试 key 和本地音频模式，没有提供测试专用 JWT secret。主工作区可能因为 `.env` 存在而通过，干净 worktree 会稳定失败。

## 修复

- `test.sh` 启动 E2E 后端时设置 `JWT_SECRET="${JWT_SECRET:-e2e-test-secret}"`。
- 增加 preflight gate，要求 E2E 启动脚本显式包含 JWT secret 配置。

## 验证

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_e2e_backend_sets_required_jwt_secret -q
JWT_SECRET=e2e-test-secret python - <<'PY'
from fastapi.testclient import TestClient
from src.api.main import app
client = TestClient(app, raise_server_exceptions=False)
r = client.post('/api/auth/register', json={'display_name': 'jwt-smoke-user'})
print(r.status_code)
PY
```

结果：gate 1/1，通过；注册 smoke 返回 200。
