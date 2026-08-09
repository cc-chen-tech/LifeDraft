"use client";

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

export function LifeReviewCard({ data }: LifeReviewCardProps) {
  const hasPersonalityLabels = data.personality_labels.length > 0;
  const hasLifeMotto = data.life_motto.trim().length > 0;
  const hasTurningPoints = data.key_turning_points.length > 0;
  const hasStats =
    data.total_decisions > 0 ||
    data.play_duration_minutes > 0 ||
    data.favorite_choice_type.trim().length > 0;
  const hasAchievements = data.achievement_badge_wall.length > 0;

  return (
    <div
      data-testid="life-review-card"
      role="group"
      aria-label="人生回顾详情"
      className="divide-y divide-[var(--border-default)]"
    >
      {hasPersonalityLabels && (
        <section className="py-6 first:pt-0">
          <h3 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
            人格标签
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.personality_labels.map((label, i) => (
              <span
                key={`${label}-${i}`}
                className="max-w-full break-words rounded-[var(--radius-pill)] border border-[var(--border-default)] bg-[var(--surface-subtle)] px-3 py-1 text-sm font-medium text-[var(--text-primary)]"
              >
                {label}
              </span>
            ))}
          </div>
        </section>
      )}

      {hasLifeMotto && (
        <section className="py-6 text-center first:pt-0">
          <p className="break-words font-serif text-lg italic leading-8 text-[var(--text-secondary)]">
            &ldquo;{data.life_motto}&rdquo;
          </p>
        </section>
      )}

      {hasTurningPoints && (
        <section className="py-6 first:pt-0">
          <h3 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
            人生转折点
          </h3>
          <ol className="divide-y divide-[var(--border-default)]">
            {data.key_turning_points.map((tp, i) => (
              <li
                key={`${tp.week}-${i}`}
                className="grid min-w-0 gap-1 py-3 text-sm sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:gap-3"
              >
                <span className="whitespace-nowrap text-xs leading-6 text-[var(--text-subtle)]">
                  第{tp.week}周
                </span>
                <span className="min-w-0 break-words leading-6 text-[var(--text-secondary)]">
                  {tp.description}
                </span>
                <span className="text-xs leading-6 text-[var(--info-foreground)] sm:text-right">
                  影响度: {Math.round(tp.impact_score * 100)}%
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {hasStats && (
        <section className="py-6 first:pt-0">
          <dl className="grid grid-cols-1 divide-y divide-[var(--border-default)] text-center sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {data.total_decisions > 0 && (
              <div className="flex min-w-0 flex-col px-3 py-3 first:pt-0 sm:py-0">
                <dt className="order-2 mt-1 text-xs text-[var(--text-subtle)]">总决策数</dt>
                <dd className="order-1 break-words text-2xl font-semibold text-[var(--text-primary)]">
                  {data.total_decisions}
                </dd>
              </div>
            )}
            {data.play_duration_minutes > 0 && (
              <div className="flex min-w-0 flex-col px-3 py-3 sm:py-0">
                <dt className="order-2 mt-1 text-xs text-[var(--text-subtle)]">游戏时长(分)</dt>
                <dd className="order-1 break-words text-2xl font-semibold text-[var(--text-primary)]">
                  {data.play_duration_minutes}
                </dd>
              </div>
            )}
            {data.favorite_choice_type.trim().length > 0 && (
              <div className="flex min-w-0 flex-col px-3 py-3 last:pb-0 sm:py-0">
                <dt className="order-2 mt-1 text-xs text-[var(--text-subtle)]">偏好风格</dt>
                <dd className="order-1 break-words text-2xl font-semibold text-[var(--text-primary)]">
                  {data.favorite_choice_type}
                </dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {hasAchievements && (
        <section data-testid="achievement-section" className="py-6 first:pt-0">
          <h3 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
            成就徽章墙 ({data.achievement_badge_wall.length})
          </h3>
          <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
            {data.achievement_badge_wall.map((badge) => (
              <AchievementBadge
                key={badge.id}
                id={badge.id}
                name={badge.name}
                description=""
                rarity={badge.rarity}
                unlockedAtWeek={badge.unlocked_at_week}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
