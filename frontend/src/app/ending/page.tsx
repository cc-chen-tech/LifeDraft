"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { PageTransition, Surface } from "@/components/story101";
import {
  getNarrativeLoadingDelay,
  NarrativeLoadingState,
} from "@/components/narrative-loading/NarrativeLoadingState";
import { LifeReviewCard, type LifeReviewData } from "@/components/game/LifeReviewCard";
import { ShareCard } from "@/components/game/ShareCard";
import { useGameStore } from "@/stores/useGameStore";
import { useHydration } from "@/hooks/useHydration";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";
import api from "@/lib/api";
import { Home, RotateCcw, Award, ChevronDown, ChevronUp } from "lucide-react";

interface EndingData {
  ending_name?: string;
  summary?: string;
  achievements?: { list: string[] };
  life_review?: LifeReviewData;
  final_stats?: {
    energy?: number;
    mood?: number;
    knowledge?: number;
    wealth?: number;
    relationships?: Record<string, number>;
  };
}

type EndingRequestState =
  | { status: "idle"; gameId: null; requestId: 0; data: null }
  | { status: "loading" | "failed"; gameId: number; requestId: number; data: null }
  | {
      status: "ready";
      gameId: number;
      requestId: number;
      data: EndingData;
    };

function isNonBlankString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isNonBlankString).map((item) => item.trim());
}

function asNumberList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is number => typeof item === "number" && Number.isFinite(item)
  );
}

function normalizeAchievements(value: unknown): string[] {
  const list = asRecord(value)?.list;
  if (!Array.isArray(list)) return [];

  return list.flatMap((item) => {
    if (isNonBlankString(item)) return [item.trim()];
    const name = asRecord(item)?.name;
    return isNonBlankString(name) ? [name.trim()] : [];
  });
}

function normalizeRelationships(value: unknown): Record<string, number> | undefined {
  const relationships = asRecord(value);
  if (!relationships) return undefined;

  const safeEntries = Object.entries(relationships).filter(
    (entry): entry is [string, number] =>
      entry[0].trim().length > 0 &&
      typeof entry[1] === "number" &&
      Number.isFinite(entry[1])
  );
  return safeEntries.length > 0 ? Object.fromEntries(safeEntries) : undefined;
}

function normalizeFinalStats(value: unknown): EndingData["final_stats"] {
  const finalStats = asRecord(value);
  if (!finalStats) return undefined;

  const normalized: NonNullable<EndingData["final_stats"]> = {};
  for (const key of ["energy", "mood", "knowledge", "wealth"] as const) {
    const amount = asFiniteNumber(finalStats[key]);
    if (amount !== undefined) normalized[key] = amount;
  }

  const relationships = normalizeRelationships(finalStats.relationships);
  if (relationships) normalized.relationships = relationships;

  return Object.keys(normalized).length > 0 ? normalized : undefined;
}

function normalizeTurningPoints(value: unknown): LifeReviewData["key_turning_points"] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const point = asRecord(item);
    const week = asFiniteNumber(point?.week);
    const impactScore = asFiniteNumber(point?.impact_score);
    const description = point?.description;
    return point && week !== undefined && impactScore !== undefined && isNonBlankString(description)
      ? [{ week, impact_score: impactScore, description: description.trim() }]
      : [];
  });
}

function normalizeBadgeWall(value: unknown): LifeReviewData["achievement_badge_wall"] {
  if (!Array.isArray(value)) return [];
  const rarities = new Set(["common", "rare", "epic", "legendary"]);

  return value.flatMap((item) => {
    const badge = asRecord(item);
    const id = badge?.id;
    const name = badge?.name;
    const rarity = badge?.rarity;
    const unlockedAtWeek = asFiniteNumber(badge?.unlocked_at_week);
    return badge &&
      isNonBlankString(id) &&
      isNonBlankString(name) &&
      typeof rarity === "string" &&
      rarities.has(rarity) &&
      unlockedAtWeek !== undefined
      ? [{
          id: id.trim(),
          name: name.trim(),
          rarity: rarity as "common" | "rare" | "epic" | "legendary",
          unlocked_at_week: unlockedAtWeek,
        }]
      : [];
  });
}

function normalizeRelationshipNetwork(
  value: unknown
): LifeReviewData["relationship_network"] {
  const network = asRecord(value);
  const rawNodes = Array.isArray(network?.nodes) ? network.nodes : [];
  const rawEdges = Array.isArray(network?.edges) ? network.edges : [];

  return {
    nodes: rawNodes.flatMap((item) => {
      const node = asRecord(item);
      const affinity = asFiniteNumber(node?.affinity);
      return node && isNonBlankString(node.name) && affinity !== undefined
        ? [{ name: node.name.trim(), affinity }]
        : [];
    }),
    edges: rawEdges.flatMap((item) => {
      const edge = asRecord(item);
      const strength = asFiniteNumber(edge?.strength);
      return edge &&
        isNonBlankString(edge.source) &&
        isNonBlankString(edge.target) &&
        strength !== undefined
        ? [{ source: edge.source.trim(), target: edge.target.trim(), strength }]
        : [];
    }),
  };
}

function normalizeLifeReview(value: unknown): LifeReviewData | undefined {
  const review = asRecord(value);
  if (!review) return undefined;

  const personalityLabels = asStringList(review.personality_labels);
  const keyTurningPoints = normalizeTurningPoints(review.key_turning_points);
  const resourceCurves = asRecord(review.resource_curves);
  const normalizedCurves = {
    energy: asNumberList(resourceCurves?.energy),
    mood: asNumberList(resourceCurves?.mood),
    knowledge: asNumberList(resourceCurves?.knowledge),
    wealth: asNumberList(resourceCurves?.wealth),
  };
  const badgeWall = normalizeBadgeWall(review.achievement_badge_wall);
  const relationshipNetwork = normalizeRelationshipNetwork(review.relationship_network);
  const lifeMotto = isNonBlankString(review.life_motto) ? review.life_motto.trim() : "";
  const playDuration = asFiniteNumber(review.play_duration_minutes);
  const totalDecisions = asFiniteNumber(review.total_decisions);
  const favoriteChoiceType = isNonBlankString(review.favorite_choice_type)
    ? review.favorite_choice_type.trim()
    : "";

  const isMeaningful =
    personalityLabels.length > 0 ||
    keyTurningPoints.length > 0 ||
    Object.values(normalizedCurves).some((curve) => curve.length > 0) ||
    badgeWall.length > 0 ||
    relationshipNetwork.nodes.length > 0 ||
    relationshipNetwork.edges.length > 0 ||
    lifeMotto.length > 0 ||
    playDuration !== undefined ||
    totalDecisions !== undefined ||
    favoriteChoiceType.length > 0;

  if (!isMeaningful) return undefined;

  return {
    personality_labels: personalityLabels,
    key_turning_points: keyTurningPoints,
    resource_curves: normalizedCurves,
    achievement_badge_wall: badgeWall,
    relationship_network: relationshipNetwork,
    life_motto: lifeMotto,
    play_duration_minutes: playDuration ?? 0,
    total_decisions: totalDecisions ?? 0,
    favorite_choice_type: favoriteChoiceType,
  };
}

function normalizeEndingResponse(value: unknown): EndingData | null {
  const response = asRecord(value);
  if (!response) return null;

  const normalized: EndingData = {};
  if (isNonBlankString(response.ending_name)) {
    normalized.ending_name = response.ending_name.trim();
  }
  if (isNonBlankString(response.summary)) {
    normalized.summary = response.summary.trim();
  }

  const achievements = normalizeAchievements(response.achievements);
  if (achievements.length > 0) normalized.achievements = { list: achievements };

  const lifeReview = normalizeLifeReview(response.life_review);
  if (lifeReview) normalized.life_review = lifeReview;

  const finalStats = normalizeFinalStats(response.final_stats);
  if (finalStats) normalized.final_stats = finalStats;

  return Object.keys(normalized).length > 0 ? normalized : null;
}

export default function EndingPage() {
  const router = useRouter();
  const { gameId, playerState, resetGame } = useGameStore();
  const [requestState, setRequestState] = useState<EndingRequestState>({
    status: "idle",
    gameId: null,
    requestId: 0,
    data: null,
  });
  const [showReview, setShowReview] = useState(false);
  const requestIdRef = useRef(0);
  const hydrated = useHydration();

  const loadEnding = useCallback(async () => {
    if (!gameId) return;

    const targetGameId = gameId;
    const requestId = ++requestIdRef.current;
    setRequestState({
      status: "loading",
      gameId: targetGameId,
      requestId,
      data: null,
    });

    try {
      const response = await api.gameplay.getEnding(targetGameId);
      if (
        requestId !== requestIdRef.current ||
        useGameStore.getState().gameId !== targetGameId
      ) {
        return;
      }

      const endingData = normalizeEndingResponse(response);
      if (!endingData) {
        setRequestState({
          status: "failed",
          gameId: targetGameId,
          requestId,
          data: null,
        });
        return;
      }

      setRequestState({
        status: "ready",
        gameId: targetGameId,
        requestId,
        data: endingData,
      });
    } catch {
      if (
        requestId === requestIdRef.current &&
        useGameStore.getState().gameId === targetGameId
      ) {
        setRequestState({
          status: "failed",
          gameId: targetGameId,
          requestId,
          data: null,
        });
      }
    }
  }, [gameId]);

  const isCurrentRequest = requestState.gameId === gameId;
  const isEndingDelayed = useDelayedLoading({
    isLoading: isCurrentRequest && requestState.status === "loading",
    delay: getNarrativeLoadingDelay("ending"),
    loadingIdentity: isCurrentRequest
      ? requestState.requestId
      : `ending:${gameId}:pending`,
  });

  useEffect(() => {
    if (!hydrated) return;
    if (!gameId) {
      router.push("/");
      return;
    }
    void loadEnding();

    return () => {
      requestIdRef.current += 1;
    };
  }, [hydrated, gameId, loadEnding, router]);

  const handleNewGame = () => {
    resetGame();
    router.push("/create");
  };

  if (!gameId) return null;

  if (isCurrentRequest && requestState.status === "failed") {
    return (
      <NarrativeLoadingState
        context="ending"
        layout="screen"
        phase="loading_context"
        transport="failed"
        onAction={() => void loadEnding()}
      />
    );
  }

  if (!isCurrentRequest || requestState.status !== "ready") {
    return (
      <NarrativeLoadingState
        context="ending"
        layout="screen"
        phase="loading_context"
        delayed={isEndingDelayed}
      />
    );
  }

  const endingData = requestState.data;

  const playerName = (playerState?.player_name as string) || "旅行者";
  const endingName = endingData.ending_name || "人生落幕";
  const endingStory = endingData.summary || "";
  const achievements = endingData.achievements?.list || [];
  const lifeReview = endingData.life_review;
  const relationships = endingData.final_stats?.relationships;

  return (
    <PageTransition className="min-h-[100dvh] bg-[var(--surface-canvas)] px-4 py-8 sm:px-6 sm:py-12">
      <Surface
        variant="reading"
        aria-labelledby="ending-title"
        className="mx-auto w-full max-w-3xl overflow-hidden"
      >
        <header className="px-5 py-8 text-center sm:px-8 sm:py-10">
          <h1
            id="ending-title"
            className="font-serif text-3xl font-semibold leading-tight text-[var(--text-primary)] sm:text-4xl"
          >
            {endingName}
          </h1>
          <p className="mt-3 break-words leading-7 text-[var(--text-secondary)]">
            {playerName}的人生旅程到此结束
          </p>
        </header>

        {(endingStory ||
          (relationships && Object.keys(relationships).length > 0) ||
          achievements.length > 0 ||
          lifeReview) && (
          <nav
            aria-label="本页内容"
            className="border-t border-[var(--border-default)] bg-[var(--surface-subtle)] px-5 py-3 sm:px-8"
          >
            <div className="flex flex-wrap items-center gap-x-2 text-sm">
              <span className="mr-1 text-[var(--text-subtle)]">本页内容</span>
              {endingStory && (
                <a
                  aria-label="终章正文"
                  href="#ending-story"
                  className="inline-flex min-h-11 min-w-11 items-center justify-center px-2 text-[var(--text-secondary)] underline-offset-4 hover:text-[var(--text-primary)] hover:underline"
                >
                  正文
                </a>
              )}
              {relationships && Object.keys(relationships).length > 0 && (
                <a
                  aria-label="人际关系"
                  href="#ending-relationships"
                  className="inline-flex min-h-11 min-w-11 items-center justify-center px-2 text-[var(--text-secondary)] underline-offset-4 hover:text-[var(--text-primary)] hover:underline"
                >
                  关系
                </a>
              )}
              {achievements.length > 0 && (
                <a
                  aria-label="人生成就"
                  href="#ending-achievements"
                  className="inline-flex min-h-11 min-w-11 items-center justify-center px-2 text-[var(--text-secondary)] underline-offset-4 hover:text-[var(--text-primary)] hover:underline"
                >
                  成就
                </a>
              )}
              {lifeReview && (
                <a
                  aria-label="人生回顾"
                  href="#ending-review"
                  className="inline-flex min-h-11 min-w-11 items-center justify-center px-2 text-[var(--text-secondary)] underline-offset-4 hover:text-[var(--text-primary)] hover:underline"
                >
                  回顾
                </a>
              )}
            </div>
          </nav>
        )}

        {endingStory && (
          <section
            id="ending-story"
            aria-labelledby="ending-story-title"
            className="border-t border-[var(--border-default)] px-5 py-7 text-left sm:px-8 sm:py-9"
          >
            <h2
              id="ending-story-title"
              className="mb-5 font-serif text-xl text-[var(--text-primary)]"
            >
              终章正文
            </h2>
            <div className="prose-story mx-auto min-w-0">
              {endingStory.split("\n\n").map((para, i) => (
                <p className="break-words" key={i}>{para}</p>
              ))}
            </div>
          </section>
        )}

        {relationships && Object.keys(relationships).length > 0 && (
          <section
            id="ending-relationships"
            aria-labelledby="ending-relationships-title"
            className="border-t border-[var(--border-default)] px-5 py-7 text-left sm:px-8 sm:py-9"
          >
            <h2
              id="ending-relationships-title"
              className="font-serif text-xl text-[var(--text-primary)]"
            >
              人际关系
            </h2>
            <dl className="mt-4 divide-y divide-[var(--border-default)]">
              {Object.entries(relationships).map(([name, affinity]) => (
                <div
                  key={name}
                  className="flex min-w-0 items-start justify-between gap-4 py-3 text-sm"
                >
                  <dt className="min-w-0 break-words leading-6 text-[var(--text-secondary)]">
                    {name}
                  </dt>
                  <dd className="shrink-0 font-medium leading-6 text-[var(--text-primary)]">
                    {affinity}/100
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        {achievements.length > 0 && (
          <section
            id="ending-achievements"
            aria-labelledby="ending-achievements-title"
            className="border-t border-[var(--border-default)] px-5 py-7 text-left sm:px-8 sm:py-9"
          >
            <h2
              id="ending-achievements-title"
              className="font-serif text-xl text-[var(--text-primary)]"
            >
              人生成就
            </h2>
            <ul className="mt-4 divide-y divide-[var(--border-default)]">
              {achievements.map((achievement, i) => (
                <li
                  key={`${achievement}-${i}`}
                  className="flex min-w-0 items-start gap-3 py-3 text-sm leading-6 text-[var(--text-secondary)]"
                >
                  <span aria-hidden="true" className="shrink-0 text-[var(--warning-foreground)]">
                    ★
                  </span>
                  <span className="min-w-0 break-words">{achievement}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {lifeReview && (
          <section
            id="ending-review"
            aria-labelledby="ending-review-title"
            className="border-t border-[var(--border-default)] px-5 py-7 text-left sm:px-8 sm:py-9"
          >
            <h2
              id="ending-review-title"
              className="font-serif text-xl text-[var(--text-primary)]"
            >
              人生回顾
            </h2>
            <Button
              type="button"
              variant="narrative"
              size="touch"
              className="mt-5 w-full"
              aria-expanded={showReview}
              aria-controls="ending-life-review"
              onClick={() => setShowReview((visible) => !visible)}
            >
              <Award className="h-4 w-4" />
              {showReview ? "隐藏人生回顾" : "查看人生回顾"}
              {showReview ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>

            {showReview && (
              <div
                id="ending-life-review"
                className="mt-7 space-y-7 border-t border-[var(--border-default)] pt-7"
              >
                <LifeReviewCard data={lifeReview} />
                <div
                  data-testid="ending-share-card-scroll-region"
                  aria-label="分享卡片预览"
                  className="max-w-full overflow-x-auto overscroll-x-contain pb-2"
                >
                  <ShareCard
                    playerName={playerName}
                    endingName={endingName}
                    lifeMotto={lifeReview.life_motto}
                    achievementCount={achievements.length}
                    playDuration={lifeReview.play_duration_minutes}
                  >
                    <div className="space-y-2 text-sm text-slate-300">
                      <p>成就数: {achievements.length}</p>
                      <p>决策数: {lifeReview.total_decisions}</p>
                    </div>
                  </ShareCard>
                </div>
              </div>
            )}
          </section>
        )}

        <div className="flex flex-col gap-3 border-t border-[var(--border-default)] px-5 py-7 sm:flex-row sm:justify-center sm:px-8 sm:py-9">
          <Button
            type="button"
            variant="narrative"
            size="touch"
            className="w-full sm:w-auto"
            onClick={() => router.push("/")}
          >
            <Home className="h-4 w-4" />
            返回首页
          </Button>
          <Button
            type="button"
            size="touch"
            className="w-full sm:w-auto"
            onClick={handleNewGame}
          >
            <RotateCcw className="h-4 w-4" />
            开始新人生
          </Button>
        </div>
      </Surface>
    </PageTransition>
  );
}
