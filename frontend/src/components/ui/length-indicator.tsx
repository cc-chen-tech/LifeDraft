import { cn } from "@/lib/utils";

interface LengthIndicatorProps {
  value: string;
  limit: number;
  className?: string;
}

export function LengthIndicator({ value, limit, className }: LengthIndicatorProps) {
  const remaining = limit - Array.from(value).length;
  const isOver = remaining < 0;

  return (
    <p
      className={cn(
        "mt-1 text-right text-xs",
        isOver ? "text-destructive" : "text-muted-foreground/70",
        className,
      )}
      role={isOver ? "alert" : undefined}
      aria-live="polite"
    >
      {isOver ? `已超出 ${Math.abs(remaining)} 字` : `还可输入 ${remaining} 字`}
    </p>
  );
}
