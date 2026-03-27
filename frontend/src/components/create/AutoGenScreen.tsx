"use client";

import { Sparkles } from "lucide-react";

interface AutoGenScreenProps {
  autoGenLabel: string;
  autoGenProgress: string;
}

export function AutoGenScreen({ autoGenLabel, autoGenProgress }: AutoGenScreenProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 animate-page-enter">
      <Sparkles className="w-14 h-14 text-primary animate-pulse mb-6" />
      <p className="text-xl text-primary font-medium animate-pulse">
        正在生成{autoGenLabel}...
      </p>
      <p className="text-sm text-muted-foreground mt-3">
        {autoGenProgress}
      </p>
      <p className="text-xs text-muted-foreground/60 mt-6">
        系统正在根据你的设定自动构建角色背景
      </p>
    </div>
  );
}
