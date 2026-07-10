"use client";

interface GenerationBudgetProgressProps {
  qualityLevel: string;
  elapsedSeconds: number;
}

const EXPECTATIONS: Record<string, { label: string; expectation: string }> = {
  fast: { label: "快速生成中", expectation: "通常 20-45 秒" },
  expert: { label: "专家生成中", expectation: "通常 45-90 秒" },
  master: { label: "大师生成中", expectation: "通常 90-180 秒" },
};

export function GenerationBudgetProgress({
  qualityLevel,
  elapsedSeconds,
}: GenerationBudgetProgressProps) {
  const progress = EXPECTATIONS[qualityLevel] ?? EXPECTATIONS.expert;
  return (
    <div
      role="status"
      aria-label={qualityLevel === "fast" ? "快速生成进度" : "故事生成进度"}
      className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
    >
      <span className="font-medium text-primary/80">{progress.label}</span>
      <span className="tabular-nums">已等待 {elapsedSeconds} 秒</span>
      <span>{progress.expectation}</span>
    </div>
  );
}
