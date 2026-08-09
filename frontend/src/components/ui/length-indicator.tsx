import { cn } from "@/lib/utils";
import { unicodeCharacterLength } from "@/lib/inputLimits";

interface LengthIndicatorProps {
  value: string;
  limit: number;
  className?: string;
}

export function LengthIndicator({ value, limit, className }: LengthIndicatorProps) {
  const remaining = limit - unicodeCharacterLength(value);
  const isOver = remaining < 0;

  return (
    <p
      className={cn(
        "mt-1 text-right text-xs",
        isOver ? "text-destructive" : "text-[var(--text-secondary)]",
        className,
      )}
      role={isOver ? "alert" : undefined}
      aria-live="polite"
    >
      {isOver ? `已超出 ${Math.abs(remaining)} 字` : `还可输入 ${remaining} 字`}
    </p>
  );
}
