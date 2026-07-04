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
    <div className="px-4 pt-2 flex gap-2 flex-shrink-0">
      <Button
        variant={activeTab === "characters" ? "default" : "outline"}
        size="sm"
        onClick={() => onTabChange("characters")}
        data-testid="collection-tab-characters"
        className="flex-1"
      >
        <User className="w-4 h-4 mr-1" />
        人物 ({charactersCount})
      </Button>
      <Button
        variant={activeTab === "items" ? "default" : "outline"}
        size="sm"
        onClick={() => onTabChange("items")}
        data-testid="collection-tab-items"
        className="flex-1"
      >
        <Package className="w-4 h-4 mr-1" />
        物品 ({itemsCount})
      </Button>
      <Button
        variant={activeTab === "landmarks" ? "default" : "outline"}
        size="sm"
        onClick={() => onTabChange("landmarks")}
        data-testid="collection-tab-landmarks"
        className="flex-1"
      >
        <MapPin className="w-4 h-4 mr-1" />
        标志物 ({landmarksCount})
      </Button>
    </div>
  );
}
