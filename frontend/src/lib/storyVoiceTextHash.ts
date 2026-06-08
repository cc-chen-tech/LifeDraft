export function normalizeStoryVoiceTextForHash(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(" ");
}

export async function storyVoiceTextToHash(text: string): Promise<string> {
  const normalized = normalizeStoryVoiceTextForHash(text);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalized));
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}
