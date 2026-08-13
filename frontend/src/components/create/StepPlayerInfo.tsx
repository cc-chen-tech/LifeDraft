"use client";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { FormField } from "@/components/story101";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";

interface StepPlayerInfoProps {
  playerName: string;
  lifeVision: string;
  onPlayerNameChange: (name: string) => void;
  onLifeVisionChange: (vision: string) => void;
  startDate?: string;
  onStartDateChange?: (date: string) => void;
}

export function StepPlayerInfo({
  playerName,
  lifeVision,
  onPlayerNameChange,
  onLifeVisionChange,
  startDate = "",
  onStartDateChange,
}: StepPlayerInfoProps) {
  const isNameOverLimit = !isWithinInputLimit(playerName, INPUT_LIMITS.name);
  const isVisionOverLimit = !isWithinInputLimit(
    lifeVision,
    INPUT_LIMITS.lifeVision,
  );

  return (
    <div className="mb-8 grid gap-6">
      <FormField id="player-name" label="角色姓名" description="故事会用这个名字称呼你。" error={isNameOverLimit ? `角色姓名不能超过 ${INPUT_LIMITS.name} 字` : undefined} required>
        {({ describedBy, invalid, required }) => <>
          <Input id="player-name" value={playerName} onChange={(e) => onPlayerNameChange(e.target.value)} placeholder="输入你的角色名" surface="underline" controlSize="touch" className="text-base" aria-describedby={[describedBy, "player-name-count"].filter(Boolean).join(" ")} aria-invalid={invalid} required={required} autoFocus />
          <LengthIndicator id="player-name-count" value={playerName} limit={INPUT_LIMITS.name} announce={false} />
        </>}
      </FormField>
      <FormField id="life-vision" label="人生愿景（可选）" description="写下你希望靠近的人生方向，也可以留空。" error={isVisionOverLimit ? `人生愿景不能超过 ${INPUT_LIMITS.lifeVision} 字` : undefined}>
        {({ describedBy, invalid }) => <>
          <Textarea id="life-vision" value={lifeVision} onChange={(e) => onLifeVisionChange(e.target.value)} placeholder="描述你希望的人生方向..." surface="underline" controlSize="touch" className="min-h-24 resize-y text-sm" aria-describedby={[describedBy, "life-vision-count"].filter(Boolean).join(" ")} aria-invalid={invalid} />
          <LengthIndicator id="life-vision-count" value={lifeVision} limit={INPUT_LIMITS.lifeVision} announce={false} />
        </>}
      </FormField>
      {onStartDateChange && (
        <div>
          <label className="text-sm text-muted-foreground mb-1 block">
            故事开始日期（可选）
          </label>
          <Input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="bg-secondary border-border h-12 text-base"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            留空时使用时代年份的 1 月 1 日
          </p>
        </div>
      )}
    </div>
  );
}
