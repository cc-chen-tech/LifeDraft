"use client";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

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
      </div>
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
      </div>
    </div>
  );
}
