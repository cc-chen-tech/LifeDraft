/**
 * SSE 轮询配置契约测试。
 * 验证前端 SSE 断开后的轮询参数符合用户体验要求。
 */
import * as fs from 'fs';
import * as path from 'path';

describe('useEventGenerator SSE 轮询配置契约', () => {
  let sourceCode: string;

  beforeAll(() => {
    const filePath = path.resolve(__dirname, '../useEventGenerator.ts');
    sourceCode = fs.readFileSync(filePath, 'utf-8');
  });

  it('maxPollingTime 应 <= 180000ms (3分钟)', () => {
    const match = sourceCode.match(/maxPollingTime\s*=\s*(\d+)/);
    expect(match).not.toBeNull();
    const value = parseInt(match![1], 10);
    expect(value).toBeLessThanOrEqual(180000);
  });

  it('pollInterval 应 <= 5000ms (5秒)', () => {
    const match = sourceCode.match(/pollInterval\s*=\s*(\d+)/);
    expect(match).not.toBeNull();
    const value = parseInt(match![1], 10);
    expect(value).toBeLessThanOrEqual(5000);
  });

  it('SSE 错误处理中应包含轮询降级逻辑', () => {
    // 验证 pollingRef 被设置为 true 的逻辑存在
    expect(sourceCode).toContain('pollingRef.current = true');
  });

  it('应存在 pollForCompletion 函数', () => {
    expect(sourceCode).toMatch(/pollForCompletion/);
  });
});
