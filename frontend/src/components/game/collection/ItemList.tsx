"use client";

import { memo, useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Package, Sparkles, Loader2 } from "lucide-react";
import { CATEGORY_LABELS } from "./types";
import type { ItemListProps } from "./types";

/**
 * 物品列表组件 - 显示所有物品卡片
 */
export const ItemList = memo(function ItemList({
  items,
  isLoading,
  onItemClick,
}: ItemListProps) {
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  const handleImageError = useCallback((name: string) => {
    setImageErrors((prev) => new Set(prev).add(name));
  }, []);
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <p className="text-muted-foreground text-sm text-center py-8">
        暂无物品记录
      </p>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {items.map((item) => (
        <button
          key={item.name}
          onClick={() => onItemClick(item)}
          className="text-left p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
        >
          {/* 图片区域 */}
          <div className="aspect-square rounded-md bg-muted mb-2 overflow-hidden flex items-center justify-center">
            {item.image_url && !imageErrors.has(item.name) ? (
              <img
                src={item.image_url}
                alt={item.name}
                loading="lazy"
                onError={() => handleImageError(item.name)}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center gap-1 text-muted-foreground">
                <Package className="w-8 h-8" />
                <span className="text-xs">无图片</span>
              </div>
            )}
          </div>

          {/* 信息 */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm truncate">
                {item.name}
              </span>
              {item.is_key_item && (
                <Sparkles className="w-3 h-3 text-amber-500" />
              )}
            </div>
            <div className="flex items-center gap-1">
              <Badge
                variant="outline"
                className="text-xs px-1.5 py-0"
              >
                {CATEGORY_LABELS[item.category] || item.category}
              </Badge>
              {!item.image_generated && (
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

ItemList.displayName = 'ItemList';
