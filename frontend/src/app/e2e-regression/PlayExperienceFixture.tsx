"use client";

import { useState } from "react";

import {
  PlayPhaseContent,
  type GameplayLoadingPresentation,
  type PlayVisualPhase,
} from "@/components/game/PlayPhaseContent";
import { PlayReadingFrame } from "@/components/game/PlayReadingFrame";
import type { PlayConstraintLevel } from "@/components/game/PlayTools";

export const playExperienceFixtureStates = [
  "options",
  "choosing",
  "result",
  "summary",
  "history",
  "reconnecting",
  "polling",
  "failed",
] as const;

export type PlayExperienceFixtureState =
  (typeof playExperienceFixtureStates)[number];

const CURRENT_STORY =
  "雨停以后，林见微沿着旧城河走到档案馆。值夜人把一封没有署名的信推到灯下，她认出纸角那道熟悉的折痕。";
const CHOOSING_STORY =
  "林见微拆开信封，先读到一句被水迹晕开的提醒。她已经作出选择，新的故事仍在继续。";
const RESULT_STORY =
  "林见微没有立刻追问来信的人。她先核对档案编号，在闭馆钟声响起前找到了一条可以继续追查的记录。";
const SUMMARY_TEXT =
  "这一周，她学会把急于求证的冲动放慢一步，也保住了与旧友之间来之不易的信任。";
const HISTORY_STORY =
  "第三周的周中，林见微在渡口收下旧友交来的账册，并答应在天亮前不向任何人透露其中的名字。";
const RECOVERY_STORY =
  "档案馆的灯还亮着，已经抵达的正文不会因为连接变化而消失。";
const ROUND_SUMMARY = "她保留了线索，也为下一步调查争取到时间。";

const OPTION_TEXTS = [
  "先核对信封上的旧邮戳，再询问值夜人是谁送来了这封信。",
  "把信暂时收好，去河边寻找纸上提到的那盏蓝色路灯。",
  "联系多年未见的旧友，请她一起判断这条线索是否值得继续追查。",
] as const;

const FIXTURE_PLAYER_STATE = {
  age: 29,
  week: 2,
  current_round: 1,
  rounds_per_week: 3,
};

function storyForState(state: PlayExperienceFixtureState) {
  switch (state) {
    case "options":
      return CURRENT_STORY;
    case "choosing":
      return CHOOSING_STORY;
    case "result":
    case "summary":
      return RESULT_STORY;
    case "history":
      return HISTORY_STORY;
    case "reconnecting":
    case "polling":
    case "failed":
      return RECOVERY_STORY;
  }
}

function phaseForState(state: PlayExperienceFixtureState): PlayVisualPhase {
  switch (state) {
    case "options":
    case "history":
      return "options";
    case "choosing":
    case "reconnecting":
    case "polling":
      return "choosing";
    case "result":
      return "result";
    case "summary":
      return "summary";
    case "failed":
      return "error";
  }
}

function recoveryAction(state: PlayExperienceFixtureState) {
  if (state === "failed") return "retry";
  if (state === "reconnecting" || state === "polling") {
    return `recover:${state}`;
  }
  return "choice-loading";
}

export function PlayExperienceFixture({
  initialState,
}: {
  initialState: PlayExperienceFixtureState;
}) {
  const [actionCount, setActionCount] = useState(0);
  const [lastAction, setLastAction] = useState("none");
  const [constraintLevel, setConstraintLevel] =
    useState<PlayConstraintLevel>("fast");
  const [narrativeStyleId, setNarrativeStyleId] = useState("");
  const [enableSceneImage, setEnableSceneImage] = useState(true);

  const recordAction = (action: string) => {
    setActionCount((count) => count + 1);
    setLastAction(action);
  };

  const phase = phaseForState(initialState);
  const isViewingHistory = initialState === "history";
  const isLoading = [
    "choosing",
    "reconnecting",
    "polling",
    "failed",
  ].includes(initialState);
  const transport: GameplayLoadingPresentation["transport"] =
    initialState === "reconnecting" ||
    initialState === "polling" ||
    initialState === "failed"
      ? initialState
      : "active";

  return (
    <PlayReadingFrame
      aria-label="游戏阅读体验回归夹具"
      data-play-state={initialState}
      data-testid="play-experience-fixture"
      playerState={FIXTURE_PLAYER_STATE}
      progress={null}
      isViewingHistory={isViewingHistory}
      toolsProps={{
        isSaving: false,
        isStoryBusy: isLoading,
        isViewingHistory,
        constraintLevel,
        narrativeStyleId,
        narrativeStyles: [
          {
            style_id: "calm",
            style_name: "克制",
            description: "让叙述保持清楚、安静。",
          },
        ],
        narrativeStylesLoading: false,
        rewriteDisabled: isLoading || isViewingHistory,
        rewriteDisabledReason: isViewingHistory
          ? "历史内容只读"
          : isLoading
            ? "故事完成后再改写"
            : undefined,
        soundAvailable: false,
        enableSceneImage,
        onSave: () => recordAction("dock:save"),
        onOpenHistory: () => recordAction("dock:history"),
        onOpenCollection: () => recordAction("dock:collection"),
        onOpenChat: () => recordAction("tools:chat"),
        onOpenRewrite: () => recordAction("tools:rewrite"),
        onOpenSummary: () => recordAction("tools:summary"),
        onRegenerate: () => recordAction("tools:regenerate"),
        onOpenSound: () => recordAction("tools:sound"),
        onHome: () => recordAction("tools:home"),
        onConstraintLevelChange: setConstraintLevel,
        onNarrativeStyleChange: setNarrativeStyleId,
        onSceneImageChange: setEnableSceneImage,
        onRequestNarrativeStyles: () => undefined,
      }}
    >
      <p className="sr-only" data-testid="play-fixture-action-count">
        {actionCount}
      </p>
      <p className="sr-only" data-testid="play-fixture-last-action">
        {lastAction}
      </p>

      <PlayPhaseContent
        phase={phase}
        isViewingHistory={isViewingHistory}
        displayText={storyForState(initialState)}
        storyStreaming={false}
        historyPosition={isViewingHistory ? { week: 2, round: 1 } : null}
        onBackToCurrent={() => recordAction("return-current")}
        loading={{
          visible: isLoading,
          phase: "streaming",
          operation: "choice",
          delayed: false,
          transport,
          onAction: () => recordAction(recoveryAction(initialState)),
        }}
        media={null}
        roundSummary={initialState === "result" ? ROUND_SUMMARY : null}
        options={
          initialState === "options"
            ? OPTION_TEXTS.map((text) => ({ text }))
            : []
        }
        onSelectChoice={(index) => recordAction(`choice:${index}`)}
        onCustomChoice={() => recordAction("custom-choice")}
        result={{
          currentRound: 1,
          roundsPerWeek: 3,
          isPrefetching: false,
          onContinue: () => recordAction("continue-result"),
        }}
        weeklySummary={{
          text: SUMMARY_TEXT,
          onContinue: () => recordAction("continue-summary"),
        }}
        inlineError={{
          visible: false,
          onRetry: () => recordAction("inline-error-retry"),
        }}
      />
    </PlayReadingFrame>
  );
}
