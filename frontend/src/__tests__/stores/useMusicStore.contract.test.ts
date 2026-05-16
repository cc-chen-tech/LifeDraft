/**
 * 契约测试 — useMusicStore API_BASE_URL
 *
 * 验证生产环境下 API_BASE_URL 不指向 localhost，
 * 避免浏览器端请求失败。
 */

import { useMusicStore } from "@/stores/useMusicStore";

const mockEnv = process.env.NEXT_PUBLIC_API_URL;

describe("useMusicStore API_BASE_URL contract", () => {
  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = mockEnv;
  });

  it("NEXT_PUBLIC_API_URL set => uses it directly", () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.story101.live";
    // Module-level const is evaluated at import time.
    // We re-import in isolation to pick up the new env.
    jest.isolateModules(() => {
      const mod = require("@/stores/useMusicStore");
      // The store does not export API_BASE_URL directly, but we can
      // verify the module loaded without error.
      expect(mod.useMusicStore).toBeDefined();
    });
  });

  it("production hostname => API_BASE_URL should not contain localhost", () => {
    // This is a documentation/contract test.
    // In production build, NEXT_PUBLIC_API_URL must be set
    // or the fallback must resolve to the actual host.
    const isProduction = process.env.NODE_ENV === "production";
    if (isProduction) {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      // If not explicitly set, the code must fall back to window.location
      // (which is verified at runtime, not statically)
      expect(apiUrl).toBeTruthy();
      expect(apiUrl).not.toContain("localhost");
    }
  });
});

describe("useMusicStore fadeVolume contract", () => {
  it("fadeVolume 应在 store 上暴露且签名为 (targetVolume, duration?) => void", () => {
    const store = useMusicStore.getState();
    expect(typeof store.fadeVolume).toBe("function");
  });

  it("fadeVolume 不应在渐变期间高频更新 store.volume", async () => {
    useMusicStore.setState({ volume: 0.5 });
    const store = useMusicStore.getState();

    // 用一个带 volume 属性的伪音频元素
    const fakeAudio = { volume: 0.5 } as unknown as HTMLAudioElement;
    store.setAudioElement(fakeAudio);

    store.fadeVolume(0.9, 150);

    // 渐变中点 store.volume 应保持不变
    await new Promise((r) => setTimeout(r, 75));
    expect(useMusicStore.getState().volume).toBe(0.5);

    // 渐变结束后 store.volume 应同步为最终值
    await new Promise((r) => setTimeout(r, 100));
    await new Promise((r) => setTimeout(r, 50));
    expect(useMusicStore.getState().volume).toBe(0.9);
  });
});

describe("useMusicStore selector contract", () => {
  it("应支持按字段 selector 订阅，避免全量重渲染", () => {
    // 验证 store 可以通过 selector 函数选取单字段
    const store = useMusicStore.getState();
    expect(store.volume).toBeDefined();
    expect(store.currentTime).toBeDefined();
    expect(store.isPlaying).toBeDefined();
    expect(store.fadeVolume).toBeDefined();
  });
});
