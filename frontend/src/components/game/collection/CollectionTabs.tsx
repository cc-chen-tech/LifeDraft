"use client";

import { Button } from "@/components/ui/button";
import { User, Package, MapPin } from "lucide-react";
import type { CollectionTabsProps } from "./types";

/**
 * 标签切换组件 - 用于在人物/物品/标志物之间切换
 */
export function CollectionTabs({
  activeTab,
  onTabChange,
  charactersCount,
  itemsCount,
  landmarksCount,
}: CollectionTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="收集分类"
      className="grid min-w-0 flex-shrink-0 grid-cols-3 px-4 pt-2"
    >
      <Button
        id="collection-tab-characters"
        type="button"
        role="tab"
        aria-selected={activeTab === "characters"}
        aria-controls="collection-panel-characters"
        variant="quiet"
        size="touch"
        onClick={() => onTabChange("characters")}
        data-testid="collection-tab-characters"
        className={`min-w-11 rounded-none border-b px-1 ${
          activeTab === "characters"
            ? "border-[var(--text-primary)] text-[var(--text-primary)]"
            : "border-[var(--border-default)]"
        }`}
      >
        <User className="h-4 w-4" />
        <span className="truncate">人物 ({charactersCount})</span>
      </Button>
      <Button
        id="collection-tab-items"
        type="button"
        role="tab"
        aria-selected={activeTab === "items"}
        aria-controls="collection-panel-items"
        variant="quiet"
        size="touch"
        onClick={() => onTabChange("items")}
        data-testid="collection-tab-items"
        className={`min-w-11 rounded-none border-b px-1 ${
          activeTab === "items"
            ? "border-[var(--text-primary)] text-[var(--text-primary)]"
            : "border-[var(--border-default)]"
        }`}
      >
        <Package className="h-4 w-4" />
        <span className="truncate">物品 ({itemsCount})</span>
      </Button>
      <Button
        id="collection-tab-landmarks"
        type="button"
        role="tab"
        aria-selected={activeTab === "landmarks"}
        aria-controls="collection-panel-landmarks"
        variant="quiet"
        size="touch"
        onClick={() => onTabChange("landmarks")}
        data-testid="collection-tab-landmarks"
        className={`min-w-11 rounded-none border-b px-1 ${
          activeTab === "landmarks"
            ? "border-[var(--text-primary)] text-[var(--text-primary)]"
            : "border-[var(--border-default)]"
        }`}
      >
        <MapPin className="h-4 w-4" />
        <span className="truncate">标志物 ({landmarksCount})</span>
      </Button>
    </div>
  );
}
