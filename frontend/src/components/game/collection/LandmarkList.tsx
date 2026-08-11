"use client";

import { memo, useState, useCallback } from "react";
import { MapPin, Loader2 } from "lucide-react";
import { LANDMARK_CATEGORY_LABELS } from "./types";
import type { LandmarkListProps } from "./types";

/**
 * 地标列表组件 - 显示所有地标卡片
 */
export const LandmarkList = memo(function LandmarkList({
  landmarks,
  isLoading,
  onLandmarkClick,
}: LandmarkListProps) {
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  const handleImageError = useCallback((name: string) => {
    setImageErrors((prev) => new Set(prev).add(name));
  }, []);
  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center py-8"
        role="status"
        aria-label="正在加载标志物收集"
      >
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (landmarks.length === 0) {
    return (
      <p className="text-muted-foreground text-sm text-center py-8">
        暂无标志物记录
      </p>
    );
  }

  return (
    <ul
      aria-label="标志物目录"
      className="w-full min-w-0 divide-y divide-[var(--border-default)] border-y border-[var(--border-default)]"
    >
      {landmarks.map((landmark) => (
        <li key={landmark.name} className="min-w-0">
          <button
            type="button"
            aria-label={`查看标志物：${landmark.name}`}
            onClick={() => onLandmarkClick(landmark)}
            className="grid min-h-11 w-full min-w-0 grid-cols-[3.5rem_minmax(0,1fr)] items-center gap-3 rounded-none py-3 text-left transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--text-primary)]"
          >
            <div className="flex h-14 w-14 items-center justify-center overflow-hidden bg-[var(--surface-subtle)]">
              {landmark.image_url && !imageErrors.has(landmark.name) ? (
                <img
                  src={landmark.image_url}
                  alt={landmark.name}
                  loading="lazy"
                  onError={() => handleImageError(landmark.name)}
                  className="h-full w-full object-cover"
                />
              ) : (
                <MapPin className="h-6 w-6 text-[var(--text-muted)]" />
              )}
            </div>

            <div className="min-w-0 space-y-1">
              <div className="flex min-w-0 items-baseline justify-between gap-3">
                <span className="truncate text-sm font-medium text-[var(--text-primary)]">
                  {landmark.name}
                </span>
                {landmark.is_key_location && (
                  <span className="shrink-0 text-xs text-[var(--text-secondary)]">
                    关键地点
                  </span>
                )}
              </div>
              <div className="flex min-w-0 items-center gap-1 text-xs text-[var(--text-secondary)]">
                <span className="truncate">
                  {LANDMARK_CATEGORY_LABELS[landmark.category] || landmark.category}
                </span>
                {!landmark.image_generated && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="shrink-0">待生成</span>
                  </>
                )}
              </div>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
});

LandmarkList.displayName = 'LandmarkList';
