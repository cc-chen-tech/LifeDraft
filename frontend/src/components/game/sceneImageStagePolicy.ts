export type SceneImageDisplayMode =
  | "event"
  | "result"
  | "result-loading"
  | "event-fallback"
  | "current"
  | "none";

export function getSceneImageDisplayMode({
  phase,
  hasEventSceneImage,
  hasResultSceneImage,
  hasCurrentRoundSceneImage,
  isLoadingRoundSceneImage,
}: {
  phase: string;
  hasEventSceneImage: boolean;
  hasResultSceneImage: boolean;
  hasCurrentRoundSceneImage: boolean;
  isLoadingRoundSceneImage: boolean;
}): SceneImageDisplayMode {
  if (phase === "options" && hasEventSceneImage) {
    return "event";
  }

  if ((phase === "result" || phase === "summary") && hasResultSceneImage) {
    return "result";
  }

  if ((phase === "result" || phase === "summary") && !hasResultSceneImage) {
    return isLoadingRoundSceneImage ? "result-loading" : hasEventSceneImage ? "event-fallback" : "none";
  }

  if (!hasEventSceneImage && !hasResultSceneImage && hasCurrentRoundSceneImage) {
    return "current";
  }

  return "none";
}
