"use client";

import { memo, useState, useCallback } from "react";
import { Package, Loader2 } from "lucide-react";
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
      <div
        className="flex items-center justify-center py-8"
        role="status"
        aria-label="正在加载物品收集"
      >
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
    <ul
      aria-label="物品目录"
      className="w-full min-w-0 divide-y divide-[var(--border-default)] border-y border-[var(--border-default)]"
    >
      {items.map((item) => (
        <li key={item.name} className="min-w-0">
          <button
            type="button"
            aria-label={`查看物品：${item.name}`}
            onClick={() => onItemClick(item)}
            className="grid min-h-11 w-full min-w-0 grid-cols-[3.5rem_minmax(0,1fr)] items-center gap-3 rounded-none py-3 text-left transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--text-primary)]"
          >
            <div className="flex h-14 w-14 items-center justify-center overflow-hidden bg-[var(--surface-subtle)]">
              {item.image_url && !imageErrors.has(item.name) ? (
                <img
                  src={item.image_url}
                  alt={item.name}
                  loading="lazy"
                  onError={() => handleImageError(item.name)}
                  className="h-full w-full object-cover"
                />
              ) : (
                <Package className="h-6 w-6 text-[var(--text-muted)]" />
              )}
            </div>

            <div className="min-w-0 space-y-1">
              <div className="flex min-w-0 items-baseline justify-between gap-3">
                <span className="truncate text-sm font-medium text-[var(--text-primary)]">
                  {item.name}
                </span>
                {item.is_key_item && (
                  <span className="shrink-0 text-xs text-[var(--text-secondary)]">
                    关键物品
                  </span>
                )}
              </div>
              <div className="flex min-w-0 items-center gap-1 text-xs text-[var(--text-secondary)]">
                <span className="truncate">
                  {CATEGORY_LABELS[item.category] || item.category}
                </span>
                {!item.image_generated && (
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

ItemList.displayName = 'ItemList';
