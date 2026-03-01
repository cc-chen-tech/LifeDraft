/**
 * useHydration — 等待 Zustand persist 从 localStorage 水合完成
 * 
 * Next.js SSR 首次渲染时，persist store 的值是默认值（如 gameId=null）。
 * 必须等水合完成后再做跳转判断，否则会误判状态为空而跳回首页。
 */
import { useState, useEffect } from "react";

export function useHydration(): boolean {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // Zustand persist 的水合在微任务级别完成，
    // 放到 useEffect 里就已经是水合后了
    setHydrated(true);
  }, []);

  return hydrated;
}
