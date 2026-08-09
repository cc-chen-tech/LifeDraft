"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
    <div className="min-h-screen bg-background animate-page-enter flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-[65ch] space-y-8 text-center">
        {/* Title */}
        <div>
          <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground mb-2">
            {endingName}
          </h1>
          <p className="text-muted-foreground">
            {playerName}的人生旅程到此结束
          </p>
        </div>

        {/* Story */}
        {endingStory && (
          <div className="prose-story text-left mx-auto">
            {endingStory.split("\n\n").map((para, i) => (
              <p key={i}>{para}</p>
            ))}
          </div>
        )}

        <Separator />

        {/* Relationships */}
        {relationships && Object.keys(relationships).length > 0 && (
          <Card className="p-4 bg-card border-border text-left">
            <h3 className="text-sm font-medium text-foreground mb-3">
              人际关系
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(relationships).map(([name, affinity]) => (
                <div
                  key={name}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-muted-foreground">{name}</span>
                  <span className="text-primary font-medium">
                    {affinity}/100
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Achievements */}
        {achievements.length > 0 && (
          <Card className="p-4 bg-card border-border text-left">
            <h3 className="text-sm font-medium text-foreground mb-2">
              人生成就
            </h3>
            <ul className="space-y-1">
              {achievements.map((achievement, i) => (
                <li
                  key={i}
                  className="text-sm text-muted-foreground flex items-start gap-2"
                >
                  <span className="text-warning">★</span>
                  {achievement}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* Life Review */}
        {lifeReview && (
          <div className="space-y-4">
            <Button
              variant="outline"
              className="w-full touch-target"
              onClick={() => setShowReview(!showReview)}
            >
              <Award className="w-4 h-4 mr-2" />
              {showReview ? "隐藏人生回顾" : "查看人生回顾"}
              {showReview ? (
                <ChevronUp className="w-4 h-4 ml-2" />
              ) : (
                <ChevronDown className="w-4 h-4 ml-2" />
              )}
            </Button>

            {showReview && (
              <div className="space-y-4 animate-page-enter">
                <LifeReviewCard data={lifeReview} />
                <ShareCard
                  playerName={playerName}
                  endingName={endingName}
                  lifeMotto={lifeReview.life_motto}
                  achievementCount={achievements.length}
                  playDuration={
                    lifeReview.play_duration_minutes
                  }
                >
                  <div className="text-sm text-slate-300 space-y-2">
                    <p>成就数: {achievements.length}</p>
                    <p>
                      决策数:{" "}
                      {lifeReview.total_decisions}
                    </p>
                  </div>
                </ShareCard>
              </div>
            )}
          </div>
        )}

        {/* Raw data fallback */}
        {!endingStory && endingData && (
          <Card className="p-4 bg-card border-border text-left">
            <pre className="text-sm text-foreground whitespace-pre-wrap font-sans">
              {JSON.stringify(endingData, null, 2)}
            </pre>
          </Card>
        )}

        {/* Actions */}
        <div className="flex gap-3 justify-center pt-4">
          <Button
            variant="outline"
            className="touch-target"
            onClick={() => router.push("/")}
          >
            <Home className="w-4 h-4 mr-2" />
            返回首页
          </Button>
          <Button className="touch-target" onClick={handleNewGame}>
            <RotateCcw className="w-4 h-4 mr-2" />
            开始新人生
          </Button>
        </div>
      </div>
    </div>
  );
}
