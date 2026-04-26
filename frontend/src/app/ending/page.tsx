"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SkeletonStory } from "@/components/game/SkeletonStory";
import { LifeReviewCard, LifeReviewData } from "@/components/game/LifeReviewCard";
import { ShareCard } from "@/components/game/ShareCard";
import { useGameStore } from "@/stores/useGameStore";
import { useHydration } from "@/hooks/useHydration";
import api from "@/lib/api";
import { Home, RotateCcw, Award, ChevronDown, ChevronUp } from "lucide-react";

export default function EndingPage() {
  const router = useRouter();
  const { gameId, playerState, resetGame } = useGameStore();
  const [endingData, setEndingData] = useState<Record<string, unknown> | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [showReview, setShowReview] = useState(false);
  const hydrated = useHydration();

  useEffect(() => {
    if (!hydrated) return;
    if (!gameId) {
      router.push("/");
      return;
    }
    api.gameplay
      .getEnding(gameId)
      .then(setEndingData)
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, [hydrated, gameId, router]);

  const handleNewGame = () => {
    resetGame();
    router.push("/create");
  };

  if (!gameId) return null;

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
  const energy = finalStats?.energy as number | undefined;
  const mood = finalStats?.mood as number | undefined;
  const knowledge = finalStats?.knowledge as number | undefined;
  const wealth = finalStats?.wealth as number | undefined;
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

        {isLoading ? (
          <SkeletonStory message="正在回顾你的一生..." />
        ) : (
          <>
            {/* Story */}
            {endingStory && (
              <div className="prose-story text-left mx-auto">
                {endingStory.split("\n\n").map((para, i) => (
                  <p key={i}>{para}</p>
                ))}
              </div>
            )}

            <Separator />

            {/* Final Stats */}
            {finalStats && (
              <div className="py-4">
                <h3 className="text-sm font-medium text-foreground mb-4">
                  最终状态
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground mb-1">精力</p>
                    <span className="text-2xl font-bold text-emerald-400">
                      {energy ?? "--"}
                    </span>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground mb-1">情绪</p>
                    <span className="text-2xl font-bold text-sky-400">
                      {mood ?? "--"}
                    </span>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground mb-1">学识</p>
                    <span className="text-2xl font-bold text-violet-400">
                      {knowledge ?? "--"}
                    </span>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground mb-1">财富</p>
                    <span className="text-2xl font-bold text-amber-400">
                      {wealth?.toLocaleString() ?? "--"}碳信用
                    </span>
                  </div>
                </div>
              </div>
            )}

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
          </>
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
