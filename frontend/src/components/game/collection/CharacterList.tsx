"use client";

import { memo, useState, useCallback } from "react";
import { User, Loader2 } from "lucide-react";
import type { CharacterListProps } from "./types";

/**
 * 人物列表组件 - 显示所有人物卡片
 */
export const CharacterList = memo(function CharacterList({
  characters,
  isLoading,
  onCharacterClick,
}: CharacterListProps) {
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  const handleImageError = useCallback((name: string) => {
    setImageErrors((prev) => new Set(prev).add(name));
  }, []);
  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center py-8"
        role="status"
        aria-label="正在加载人物收集"
      >
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
    <ul
      aria-label="人物目录"
      className="w-full min-w-0 divide-y divide-[var(--border-default)] border-y border-[var(--border-default)]"
    >
      {characters.map((character) => (
        <li key={character.name} className="min-w-0">
          <button
            type="button"
            aria-label={`查看人物：${character.name}`}
            onClick={() => onCharacterClick(character)}
            className="grid min-h-11 w-full min-w-0 grid-cols-[3.5rem_minmax(0,1fr)] items-center gap-3 rounded-none py-3 text-left transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--text-primary)]"
          >
            <div className="flex h-14 w-14 items-center justify-center overflow-hidden bg-[var(--surface-subtle)]">
              {character.image_url && !imageErrors.has(character.name) ? (
                <img
                  src={character.image_url}
                  alt={character.name}
                  className="h-full w-full object-contain"
                  loading="lazy"
                  onError={() => handleImageError(character.name)}
                />
              ) : (
                <User className="h-6 w-6 text-[var(--text-muted)]" />
              )}
            </div>

            <div className="min-w-0 space-y-1">
              <div className="flex min-w-0 items-baseline justify-between gap-3">
                <span className="truncate text-sm font-medium text-[var(--text-primary)]">
                  {character.name}
                </span>
                <span className="shrink-0 text-xs text-[var(--text-secondary)]">
                  {character.image_generated ? "有图" : "待生成"}
                </span>
              </div>
              {character.role && (
                <p className="truncate text-xs text-[var(--text-secondary)]">
                  {character.role}
                </p>
              )}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
});

CharacterList.displayName = 'CharacterList';
