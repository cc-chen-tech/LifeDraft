/** Unicode code-point measurement shared by UI feedback and submit guards. */
export function unicodeCharacterLength(value: string): number {
  return Array.from(value).length;
}

export function isWithinInputLimit(value: string, limit: number): boolean {
  return unicodeCharacterLength(value) <= limit;
}
