import { normalizeStoryTextForHash, storyTextToHash } from "@/lib/storyTextHash";

describe("storyTextHash", () => {
  it("normalizes whitespace and CRLF to stable input", () => {
    const raw = "雨夜起风,\r\n    账册被风吹开。\n第二句";
    const normalized = normalizeStoryTextForHash(raw);
    expect(normalized).toBe("雨夜起风,账册被风吹开。第二句");
  });

  it("produces same hash for equivalent whitespace formats", () => {
    const hash1 = storyTextToHash("雨夜起风，账册被风吹开。");
    const hash2 = storyTextToHash("雨夜起风，\n账册被风吹开。");
    const hash3 = storyTextToHash("雨夜起风，  账册被风吹开。 ");
    expect(hash1).toBe(hash2);
    expect(hash2).toBe(hash3);
  });

  it("produces consistent and different hashes for different text", () => {
    const hash1 = storyTextToHash("A");
    const hash2 = storyTextToHash("B");
    expect(hash1).not.toBe(hash2);
    expect(storyTextToHash("")).toBe("0");
  });
});
