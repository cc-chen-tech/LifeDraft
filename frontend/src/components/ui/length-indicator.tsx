import { cn } from "@/lib/utils";
import { unicodeCharacterLength } from "@/lib/inputLimits";

interface LengthIndicatorProps {
  value: string;
  limit: number;
  id?: string;
  announce?: boolean;
  className?: string;
}

export function LengthIndicator({
  value,
  limit,
  id,
  announce = true,
  className,
}: LengthIndicatorProps) {
  const remaining = limit - unicodeCharacterLength(value);
  const isOver = remaining < 0;

  return (
    <p
      id={id}
      className={cn(
        "mt-1 text-right text-xs",
        isOver ? "text-destructive" : "text-[var(--text-secondary)]",
        className,
      )}
      role={announce && isOver ? "alert" : undefined}
      aria-live={announce ? "polite" : undefined}
    >
      {isOver ? `已超出 ${Math.abs(remaining)} 字` : `还可输入 ${remaining} 字`}
    </p>
  );
}
