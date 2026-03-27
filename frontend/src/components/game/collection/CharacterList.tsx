"use client";

import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { User, Image as ImageIcon, Loader2 } from "lucide-react";
import type { CharacterListProps } from "./types";

/**
 * 人物列表组件 - 显示所有人物卡片
 */
export const CharacterList = memo(function CharacterList({
  characters,
  isLoading,
  onCharacterClick,
}: CharacterListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (characters.length === 0) {
    return (
      <p className="text-muted-foreground text-sm text-center py-8">
        暂无人物记录
      </p>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {characters.map((character) => (
        <button
          key={character.name}
          onClick={() => onCharacterClick(character)}
          className="text-left p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
        >
          {/* 图片区域 - 使用 object-top 确保显示头部 */}
          <div className="aspect-[3/4] rounded-md bg-muted mb-2 overflow-hidden flex items-center justify-center">
            {character.image_url ? (
              <img
                src={character.image_url}
                alt={character.name}
                className="w-full h-full object-cover object-top"
              />
            ) : (
              <div className="flex flex-col items-center gap-1 text-muted-foreground">
                <User className="w-8 h-8" />
                <span className="text-xs">无图片</span>
              </div>
            )}
          </div>

          {/* 信息 */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm truncate">
                {character.name}
              </span>
              {character.image_generated ? (
                <Badge variant="outline" className="text-xs">
                  <ImageIcon className="w-3 h-3 mr-1" />
                  有图
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-xs">
                  待生成
                </Badge>
              )}
            </div>
            {character.role && (
              <p className="text-xs text-muted-foreground truncate">
                {character.role}
              </p>
            )}
          </div>
        </button>
      ))}
    </div>
  );
});

CharacterList.displayName = 'CharacterList';
