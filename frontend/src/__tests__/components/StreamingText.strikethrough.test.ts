/**
 * StreamingText strikethrough 处理测试
 *
 * 验证 stripIncompleteMarkdown 能正确处理 ~~strikethrough~~ 语法，
 * 避免流式输出中未闭合的 ~~ 触发删除线渲染。
 */

import { stripIncompleteMarkdown } from "@/components/game/StreamingText";

describe("stripIncompleteMarkdown — strikethrough", () => {
  it("应保留完整的 ~~text~~", () => {
    const text = "这是 ~~删除线~~ 文本";
    expect(stripIncompleteMarkdown(text)).toBe(text);
  });

  it("应移除末尾未闭合的 ~~", () => {
    // ~~ 必须位于文本末尾附近才会被移除
    const text = "这是 ~~";
    expect(stripIncompleteMarkdown(text)).toBe("这是 ");
  });

  it("中间未闭合的 ~~ 不应被移除（后续文本会闭合）", () => {
    const text = "这是 ~~未闭合但后面还有内容";
    expect(stripIncompleteMarkdown(text)).toBe(text);
  });

  it("应移除末尾单独的 ~", () => {
    const text = "末尾有一个波浪号~";
    expect(stripIncompleteMarkdown(text)).toBe("末尾有一个波浪号");
  });

  it("奇数个 ~~ 且最后一个位于末尾时应移除", () => {
    const text = "~~opened~~ but ~~";
    expect(stripIncompleteMarkdown(text)).toBe("~~opened~~ but ");
  });

  it("偶数个 ~~ 保持完整", () => {
    const text = "~~deleted~~ and ~~also deleted~~";
    expect(stripIncompleteMarkdown(text)).toBe(text);
  });

  it("空字符串应安全返回", () => {
    expect(stripIncompleteMarkdown("")).toBe("");
  });

  it("不含 markdown 的文本保持不变", () => {
    const text = "普通文本没有任何标记";
    expect(stripIncompleteMarkdown(text)).toBe(text);
  });

  it("中文文本末尾的 ~ 会被移除（已知行为， narrative 文本中风险低）", () => {
    // ★ 契约说明：单字 ~ 在末尾会被当作未完成的 strikethrough 移除。
    // 在正式叙事文本中，~ 极少作为语气词出现在句尾；
    // 若未来需要保留，可将此条件改为检查前方是否有配对 ~。
    const text = "今天天气真好~";
    expect(stripIncompleteMarkdown(text)).toBe("今天天气真好");
  });

  it("中文文本中间的 ~ 不会被移除", () => {
    const text = "价格~500~元";
    expect(stripIncompleteMarkdown(text)).toBe(text);
  });
});

describe("stripIncompleteMarkdown — 其他 markdown 标记", () => {
  it("应移除末尾未闭合的 **", () => {
    expect(stripIncompleteMarkdown("粗体**")).toBe("粗体");
  });

  it("开头的 ** 不应被移除（是开始标记）", () => {
    expect(stripIncompleteMarkdown("**粗体未闭合")).toBe("**粗体未闭合");
  });

  it("应保留闭合的 **", () => {
    expect(stripIncompleteMarkdown("**粗体**")).toBe("**粗体**");
  });

  it("应移除末尾单独的 *", () => {
    expect(stripIncompleteMarkdown("斜体*")).toBe("斜体");
  });

  it("应移除末尾未闭合的 `", () => {
    expect(stripIncompleteMarkdown("代码`")).toBe("代码");
  });

  it("应保留闭合的 `` ` ``", () => {
    expect(stripIncompleteMarkdown("`code`")).toBe("`code`");
  });
});
