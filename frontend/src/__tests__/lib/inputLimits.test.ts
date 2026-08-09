import { isWithinInputLimit, unicodeCharacterLength } from "@/lib/inputLimits";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

describe("Unicode input limits", () => {
  it("counts astral emoji as one Unicode character like the backend", () => {
    expect(unicodeCharacterLength("😀".repeat(INPUT_LIMITS.name))).toBe(INPUT_LIMITS.name);
    expect(isWithinInputLimit("😀".repeat(INPUT_LIMITS.name), INPUT_LIMITS.name)).toBe(true);
    expect(isWithinInputLimit("😀".repeat(INPUT_LIMITS.name + 1), INPUT_LIMITS.name)).toBe(false);
  });
});
