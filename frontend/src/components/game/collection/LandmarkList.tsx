"use client";

import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { MapPin, Sparkles, Loader2 } from "lucide-react";
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
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
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
    <div className="grid grid-cols-2 gap-3">
      {landmarks.map((landmark) => (
        <button
          key={landmark.name}
          onClick={() => onLandmarkClick(landmark)}
          className="text-left p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
        >
          {/* 图片区域 */}
          <div className="aspect-video rounded-md bg-muted mb-2 overflow-hidden flex items-center justify-center">
            {landmark.image_url ? (
              <img
                src={landmark.image_url}
                alt={landmark.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center gap-1 text-muted-foreground">
                <MapPin className="w-8 h-8" />
                <span className="text-xs">无图片</span>
              </div>
            )}
          </div>

          {/* 信息 */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm truncate">
                {landmark.name}
              </span>
              {landmark.is_key_location && (
                <Sparkles className="w-3 h-3 text-amber-500" />
              )}
            </div>
            <div className="flex items-center gap-1">
              <Badge
                variant="outline"
                className="text-xs px-1.5 py-0"
              >
                {LANDMARK_CATEGORY_LABELS[landmark.category] || landmark.category}
              </Badge>
              {!landmark.image_generated && (
                <Badge variant="secondary" className="text-xs px-1.5 py-0">
                  待生成
                </Badge>
              )}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
});

LandmarkList.displayName = 'LandmarkList';
