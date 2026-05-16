'use client';
import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
    // 上报错误到 Sentry（仅在 DSN 配置时生效）
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <h2 className="text-xl font-semibold">出现了一些问题</h2>
      <button onClick={reset} className="px-4 py-2 bg-primary text-white rounded">
        重试
      </button>
    </div>
  );
}
