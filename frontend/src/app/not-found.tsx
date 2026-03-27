import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <h2 className="text-2xl font-semibold">页面未找到</h2>
      <p className="text-muted-foreground">抱歉，您访问的页面不存在</p>
      <Link 
        href="/" 
        className="px-4 py-2 bg-primary text-white rounded hover:bg-primary/90 transition-colors"
      >
        返回首页
      </Link>
    </div>
  );
}
