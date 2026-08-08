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
import { LifeReviewCard, LifeReviewData } from "@/components/game/LifeReviewCard";
import { ShareCard } from "@/components/game/ShareCard";
import { useGameStore } from "@/stores/useGameStore";
import { useHydration } from "@/hooks/useHydration";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";
import api from "@/lib/api";
import { Home, RotateCcw, Award, ChevronDown, ChevronUp } from "lucide-react";

type EndingRequestState = "idle" | "loading" | "ready" | "failed";

function isEndingResponse(value: unknown): value is Record<string, unknown> {
  return Boolean(
    value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      Object.keys(value).length > 0
  );
}

export default function EndingPage() {
  const router = useRouter();
  const { gameId, playerState, resetGame } = useGameStore();
  const [endingData, setEndingData] = useState<Record<string, unknown> | null>(
    null
  );
  const [requestState, setRequestState] = useState<EndingRequestState>("idle");
  const [requestIdentity, setRequestIdentity] = useState(0);
  const [showReview, setShowReview] = useState(false);
  const requestIdRef = useRef(0);
  const hydrated = useHydration();

  const loadEnding = useCallback(async () => {
    if (!gameId) return;

    const requestId = ++requestIdRef.current;
    setRequestIdentity(requestId);
    setRequestState("loading");
    setEndingData(null);

    try {
      const response = await api.gameplay.getEnding(gameId);
      if (requestId !== requestIdRef.current) return;

      if (!isEndingResponse(response)) {
        setRequestState("failed");
        return;
      }

      setEndingData(response);
      setRequestState("ready");
    } catch {
      if (requestId === requestIdRef.current) {
        setRequestState("failed");
      }
    }
  }, [gameId]);

  const isEndingDelayed = useDelayedLoading({
    isLoading: requestState === "loading",
    delay: getNarrativeLoadingDelay("ending"),
    loadingIdentity: requestIdentity,
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

  if (requestState === "idle" || requestState === "loading") {
    return (
      <NarrativeLoadingState
        context="ending"
        layout="screen"
        phase="loading_context"
        delayed={isEndingDelayed}
      />
    );
  }

  if (requestState === "failed") {
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

  const playerName = (playerState?.player_name as string) || "旅行者";
  const endingName = (endingData?.ending_name as string) || "人生落幕";
  const endingStory = (endingData?.summary as string) || "";
  const achievements = (
    endingData?.achievements as { list?: Record<string, unknown>[] }
  )?.list || [];
  const lifeReview = endingData?.life_review as
    | Record<string, unknown>
    | undefined;

  const finalStats = endingData?.final_stats as
    | Record<string, unknown>
    | undefined;
  const relationships = finalStats?.relationships as
    | Record<string, number>
    | undefined;

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
              {achievements.map((achievement: Record<string, unknown>, i: number) => (
                <li
                  key={i}
                  className="text-sm text-muted-foreground flex items-start gap-2"
                >
                  <span className="text-warning">★</span>
                  {(achievement.name as string) || String(achievement)}
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
                <LifeReviewCard data={lifeReview as unknown as LifeReviewData} />
                <ShareCard
                  playerName={playerName}
                  endingName={endingName}
                  lifeMotto={(lifeReview?.life_motto as string) || ""}
                  achievementCount={achievements.length}
                  playDuration={
                    (lifeReview?.play_duration_minutes as number) || 0
                  }
                >
                  <div className="text-sm text-slate-300 space-y-2">
                    <p>成就数: {achievements.length}</p>
                    <p>
                      决策数:{" "}
                      {(lifeReview?.total_decisions as number) || 0}
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
