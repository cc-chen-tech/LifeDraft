import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { GlobalStatePage } from '@/components/story101';

export default function NotFound() {
  return (
    <GlobalStatePage
      title="页面未找到"
      description="抱歉，您访问的页面不存在。"
      action={
        <Button asChild variant="chrome" size="touch">
          <Link href="/">返回首页</Link>
        </Button>
      }
    />
  );
}
