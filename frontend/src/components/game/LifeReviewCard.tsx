"use client";

import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AchievementBadge } from "./AchievementBadge";

interface BadgeWallItem {
  id: string;
  name: string;
  rarity: "common" | "rare" | "epic" | "legendary";
  unlocked_at_week: number;
}

interface TurningPoint {
  week: number;
  description: string;
  impact_score: number;
}

export interface LifeReviewData {
  personality_labels: string[];
  key_turning_points: TurningPoint[];
  resource_curves: {
    energy: number[];
    mood: number[];
    knowledge: number[];
    wealth: number[];
  };
  achievement_badge_wall: BadgeWallItem[];
  relationship_network: {
    nodes: { name: string; affinity: number }[];
    edges: { source: string; target: string; strength: number }[];
  };
  life_motto: string;
  play_duration_minutes: number;
  total_decisions: number;
  favorite_choice_type: string;
}

interface LifeReviewCardProps {
  data: LifeReviewData;
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 120;
  const height = 30;
  const step = width / (data.length - 1);

  const points = data
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function LifeReviewCard({ data }: LifeReviewCardProps) {
  const curveColors = {
    energy: "#34d399",
    mood: "#38bdf8",
    knowledge: "#a78bfa",
    wealth: "#fbbf24",
  };

  return (
    <Card
      data-testid="life-review-card"
      className="p-6 space-y-6 bg-card border-border"
    >
      {/* Personality Labels */}
      <div>
        <h3 className="text-sm font-medium text-foreground mb-3">人格标签</h3>
        <div className="flex flex-wrap gap-2">
          {data.personality_labels.map((label, i) => (
            <span
              key={i}
              className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium"
            >
              {label}
            </span>
          ))}
        </div>
      </div>

      <Separator />

      {/* Life Motto */}
      <div className="text-center py-2">
        <p className="text-lg font-serif italic text-muted-foreground">
          &ldquo;{data.life_motto}&rdquo;
        </p>
      </div>

      <Separator />

      {/* Resource Curves */}
      <div>
        <h3 className="text-sm font-medium text-foreground mb-3">资源曲线</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(data.resource_curves).map(([key, values]) => (
            <div key={key} className="text-center">
              <p className="text-xs text-muted-foreground capitalize mb-1">
                {key}
              </p>
              <MiniSparkline
                data={values}
                color={curveColors[key as keyof typeof curveColors]}
              />
              <p className="text-sm font-semibold mt-1">
                {values[values.length - 1]}
              </p>
            </div>
          ))}
        </div>
      </div>

      <Separator />

      {/* Key Turning Points */}
      {data.key_turning_points.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-foreground mb-3">
            人生转折点
          </h3>
          <div className="space-y-2">
            {data.key_turning_points.map((tp, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  第{tp.week}周
                </span>
                <span className="text-muted-foreground">{tp.description}</span>
                <span className="text-xs text-primary ml-auto">
                  影响度: {Math.round(tp.impact_score * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Separator />

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-2xl font-bold text-foreground">
            {data.total_decisions}
          </p>
          <p className="text-xs text-muted-foreground">总决策数</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-foreground">
            {data.play_duration_minutes}
          </p>
          <p className="text-xs text-muted-foreground">游戏时长(分)</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-foreground">
            {data.favorite_choice_type}
          </p>
          <p className="text-xs text-muted-foreground">偏好风格</p>
        </div>
      </div>

      <Separator />

      {/* Achievement Badge Wall */}
      {data.achievement_badge_wall.length > 0 && (
        <div data-testid="achievement-section">
          <h3 className="text-sm font-medium text-foreground mb-3">
            成就徽章墙 ({data.achievement_badge_wall.length})
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {data.achievement_badge_wall.map((badge, i) => (
              <AchievementBadge
                key={badge.id}
                id={badge.id}
                name={badge.name}
                description=""
                rarity={badge.rarity}
                unlockedAtWeek={badge.unlocked_at_week}
                animate={true}
                delay={i * 150}
              />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
