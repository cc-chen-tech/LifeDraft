# Frontend (Next.js)

> 最后更新：2026-04-26

本目录是游戏前端应用，技术栈：

- Next.js 16（App Router）
- React 19
- TypeScript
- Zustand
- Jest + Playwright

## 开发启动

```bash
npm install
npm run dev
```

默认访问：`http://localhost:3000`

## 常用命令

```bash
npm run dev
npm run build
npm run start
npm run lint
npm test
npm run test:e2e
npm run test:types
```

## API 与代理

前端默认通过同域 `/api/*` 调用后端。  
代理入口：`src/app/api/[...path]/route.ts`（负责 Cookie 转发、SSE/流式透传、超时处理）。

## 类型契约同步

后端接口变更后请同步类型：

```bash
npm run sync:api-types
```

该命令会：

1. 调用后端导出 OpenAPI schema
2. 生成 `src/types/api-generated.d.ts`

## 测试结构说明

- 单元/集成：`src/__tests__/`
- E2E：`e2e/`
- 集成测试补充说明：`src/__tests__/integration/README.md`

## 相关文档

- 仓库根文档：`../README.md`
- 项目 wiki：`../docs/wiki/README.md`
