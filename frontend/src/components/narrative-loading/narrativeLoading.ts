export type NarrativeLoadingContext =
  | "hydrate"
  | "character-step"
  | "character-auto"
  | "opening"
  | "gameplay"
  | "ending";

export type NarrativeLoadingLayout = "screen" | "section" | "inline";
export type NarrativeLoadingOperation = "event" | "choice";
export type NarrativeTransportState = "active" | "reconnecting" | "polling" | "failed";

export interface NarrativeLoadingCopyOptions {
  context: NarrativeLoadingContext;
  phase?: string | null;
  operation?: NarrativeLoadingOperation;
  stepLabel?: string;
  contextLabel?: string;
  delayed?: boolean;
  transport?: NarrativeTransportState;
}

export interface NarrativeLoadingCopy {
  title: string;
  status?: string;
  delayedCopy?: string;
  actionLabel?: "重新连接" | "重试";
}

const TITLES: Record<NarrativeLoadingContext, string> = {
  hydrate: "正在打开这一页",
  "character-step": "角色设定，正在成形",
  "character-auto": "角色背景，正在补全",
  opening: "人生开篇，正在落笔",
  gameplay: "下一页，正在展开",
  ending: "这一生，正在收束",
};

const PHASE_GROUPS: Record<string, string> = {
  preparing: "正在准备",
  resuming: "正在准备",
  initializing: "正在准备",
  loading_context: "正在梳理",
  building_world: "正在梳理",
  generating: "正在写作",
  generating_story: "正在写作",
  retry: "正在写作",
  retrying: "正在写作",
  validating: "正在校对",
  generating_options: "正在准备选择",
};

const QUALITY_DELAYS: Record<string, number> = {
  fast: 45_000,
  expert: 90_000,
  master: 180_000,
};

const APPROVED_EXTERNAL_LABELS = new Set([
  "时代背景",
  "年龄阶段",
  "性别",
  "世界观",
  "人物形象",
  "家庭背景",
  "人际关系",
  "性格特征",
  "财富状况",
  "剩余角色背景",
  "生成关键人物",
  "整理人际关系",
]);

function fallbackStatus(operation?: NarrativeLoadingOperation) {
  return operation === "choice" ? "正在继续推演" : "正在继续写作";
}

function getAllowedLabel(label?: string): string | undefined {
  const trimmedLabel = label?.trim();
  return trimmedLabel && APPROVED_EXTERNAL_LABELS.has(trimmedLabel) ? trimmedLabel : undefined;
}

function getActionLabel(transport: NarrativeTransportState): NarrativeLoadingCopy["actionLabel"] {
  if (transport === "failed") return "重试";
  if (transport === "reconnecting" || transport === "polling") return "重新连接";
  return undefined;
}

export function resolveNarrativeLoadingCopy({
  context,
  phase,
  operation,
  stepLabel,
  contextLabel,
  delayed = false,
  transport,
}: NarrativeLoadingCopyOptions): NarrativeLoadingCopy {
  const normalizedPhase = phase?.trim().toLowerCase();
  const retryProgress = normalizedPhase?.match(/^retry:(\d+)\/(\d+)$/);
  const resolvedTransport = transport ?? "active";
  const label = getAllowedLabel(stepLabel) ?? getAllowedLabel(contextLabel);
  const status =
    context === "hydrate" || normalizedPhase === "completed"
      ? undefined
      : label ??
        (retryProgress
          ? `正在写作（第 ${retryProgress[1]}/${retryProgress[2]} 次）`
          : normalizedPhase
            ? PHASE_GROUPS[normalizedPhase] ?? fallbackStatus(operation)
            : undefined);

  return {
    title: TITLES[context],
    status,
    delayedCopy: delayed ? "这一页仍在继续写作" : undefined,
    actionLabel: getActionLabel(resolvedTransport),
  };
}

export function getNarrativeLoadingDelay(
  context: NarrativeLoadingContext,
  qualityLevel?: string
): number {
  switch (context) {
    case "hydrate":
      return 250;
    case "character-step":
    case "ending":
      return 15_000;
    case "character-auto":
      return 30_000;
    case "opening":
    case "gameplay":
      return QUALITY_DELAYS[qualityLevel?.toLowerCase() ?? "fast"] ?? QUALITY_DELAYS.fast;
  }
}
