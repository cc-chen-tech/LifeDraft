"use client";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

interface StepPlayerInfoProps {
  playerName: string;
  lifeVision: string;
  onPlayerNameChange: (name: string) => void;
  onLifeVisionChange: (vision: string) => void;
}

export function StepPlayerInfo({
  playerName,
  lifeVision,
  onPlayerNameChange,
  onLifeVisionChange,
}: StepPlayerInfoProps) {
  return (
    <div className="space-y-4 mb-8">
      <div>
        <label className="text-sm text-muted-foreground mb-1 block">
          角色姓名
        </label>
        <Input
          value={playerName}
          onChange={(e) => onPlayerNameChange(e.target.value)}
          placeholder="输入你的角色名"
          className="bg-secondary border-border h-12 text-base"
          autoFocus
        />
        <LengthIndicator value={playerName} limit={INPUT_LIMITS.name} />
      </div>
      <div>
        <label className="text-sm text-muted-foreground mb-1 block">
          人生愿景（可选）
        </label>
        <Textarea
          value={lifeVision}
          onChange={(e) => onLifeVisionChange(e.target.value)}
          placeholder="描述你希望的人生方向..."
          className="bg-secondary border-border text-sm resize-none min-h-[80px]"
        />
        <LengthIndicator value={lifeVision} limit={INPUT_LIMITS.lifeVision} />
      </div>
    </div>
  );
}
