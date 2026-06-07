import {
  normalizeStoryVoiceTextForHash,
  storyVoiceTextToHash,
} from "@/lib/storyVoiceTextHash";
import { webcrypto } from "node:crypto";

describe("storyVoiceTextHash", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "crypto", {
      value: webcrypto,
      configurable: true,
    });
  });

  it("matches the backend voice-reading SHA-256 hash normalization", async () => {
    expect(normalizeStoryVoiceTextForHash("一段\n 当前   故事。")).toBe("一段 当前 故事。");

    await expect(storyVoiceTextToHash("一段当前故事。")).resolves.toBe(
      "95813215c6b945ae5e1746a1219579a9884fd99997cf398d046f071a819c149e"
    );
  });
});
