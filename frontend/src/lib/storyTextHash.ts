/**
 * 生成稳定文本哈希键，用于故事文本去重。
 */
export function normalizeStoryTextForHash(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\s+/g, " ")
    .replace(/([,，。.。;:!?！？!])\s+/g, "$1")
    .replace(/\s+([,，。.。;:!?！？!])/g, "$1")
    .trim();
}

export function storyTextToHash(text: string): string {
  const normalized = normalizeStoryTextForHash(text);

  if (!normalized) {
    return "0";
  }

  let hash = 5381;
  for (let i = 0; i < normalized.length; i++) {
    hash = (hash * 33) ^ normalized.charCodeAt(i);
    hash = hash >>> 0;
  }

  return hash.toString(16);
}
