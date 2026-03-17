/**
 * useHydration — 等待客户端渲染完成
 *
 * Next.js SSR 首次渲染时，状态是默认值。
 * 必须等客户端渲染完成后再做跳转判断，否则会误判状态为空而跳回首页。
 */
import { useState, useEffect } from "react";

export function useHydration(): boolean {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // 客户端渲染完成后标记为 hydrated
    setHydrated(true);
  }, []);

  return hydrated;
}
