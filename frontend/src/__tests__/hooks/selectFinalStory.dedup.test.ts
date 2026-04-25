/**
 * selectFinalStory 去重测试
 *
 * 验证当前端 story 已经是后端 story 的完整前缀时，
 * 不会重复追加文本。
 */

import { selectFinalStory } from "@/hooks/game/eventUtils";

describe("selectFinalStory — 防止文本重复", () => {
  it("前端是后端的完整前缀时应只返回剩余部分", () => {
    const frontend = "第一章：开局。你走进森林，看到一条小路。";
    const backend = "第一章：开局。你走进森林，看到一条小路。然后你继续前行。";
    const result = selectFinalStory(backend, frontend);

    expect(result.useBackend).toBe(false);
    expect(result.finalStory).toBe(frontend);
    expect(result.remainingText).toBe("然后你继续前行。");
  });

  it("前端和后端完全一致时不应返回 remainingText", () => {
    const story = "第一章：开局。第二章：冒险。";
    const result = selectFinalStory(story, story);

    expect(result.useBackend).toBe(false);
    expect(result.finalStory).toBe(story);
    expect(result.remainingText).toBeUndefined();
  });

  it("前端不是后端的前缀时应直接使用后端故事", () => {
    // 后端重写/ divergence 的情况
    const frontend = "第一章：开局。你走左边。";
    const backend = "第一章：开局。你走右边。第二章：发现宝藏。";
    const result = selectFinalStory(backend, frontend);

    // 前端不是后端的前缀，不应尝试切片追加
    expect(result.useBackend).toBe(true);
    expect(result.finalStory).toBe(backend);
    expect(result.remainingText).toBeUndefined();
  });

  it("前端极短时应直接使用后端故事", () => {
    const result = selectFinalStory("很长的后端故事", "短");
    expect(result.useBackend).toBe(true);
    expect(result.finalStory).toBe("很长的后端故事");
  });

  it("后端明显短于前端时应优先前端", () => {
    const frontend = "很长的前端流式故事，已经累积了很多内容";
    const backend = "短 fallback";
    const result = selectFinalStory(backend, frontend);

    expect(result.useBackend).toBe(false);
    expect(result.finalStory).toBe(frontend);
  });

  it("后端为空时应使用前端", () => {
    const result = selectFinalStory("", "前端故事");
    expect(result.useBackend).toBe(false);
    expect(result.finalStory).toBe("前端故事");
  });
});
