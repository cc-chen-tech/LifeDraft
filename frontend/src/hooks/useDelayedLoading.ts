"use client";

import { useEffect, useRef, useState } from "react";

export interface DelayedLoadingOptions {
  isLoading: boolean;
  delay: number;
  loadingIdentity: string | number | null | undefined;
}

export function useDelayedLoading({
  isLoading,
  delay,
  loadingIdentity,
}: DelayedLoadingOptions): boolean {
  const [isVisible, setIsVisible] = useState(false);
  const delayRef = useRef(delay);

  useEffect(() => {
    delayRef.current = delay;
  }, [delay]);

  useEffect(() => {
    if (!isLoading) {
      setIsVisible(false);
      return;
    }

    setIsVisible(false);
    const timeoutId = window.setTimeout(() => setIsVisible(true), delayRef.current);
    return () => window.clearTimeout(timeoutId);
  }, [isLoading, loadingIdentity]);

  return isVisible;
}
