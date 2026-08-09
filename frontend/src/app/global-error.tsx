'use client';
import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { GlobalStatePage } from '@/components/story101';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        <GlobalStatePage
          title="出现了一些问题"
          description="这一页暂时无法继续。请再试一次。"
          action={<Button type="button" variant="chrome" size="touch" onClick={reset}>重试</Button>}
        />
      </body>
    </html>
  );
}
