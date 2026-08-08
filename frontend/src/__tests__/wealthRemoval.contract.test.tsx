import { render, screen } from "@testing-library/react";

import { SettingDisplay } from "@/components/game/SettingDisplay";
import type { LifeReviewData } from "@/components/game/LifeReviewCard";
import type { EffectValues, PlayerState } from "@/lib/types";
import { AUTO_ADVANCE_STEPS } from "@/stores/useCharacterStore";

describe("wealth removal public contracts", () => {
  it("finishes character generation after traits", () => {
    expect(AUTO_ADVANCE_STEPS).toEqual(["family", "relationships", "traits"]);
  });

  it("does not render a legacy wealth setting", () => {
    const { container } = render(
      <SettingDisplay
        stepKey="wealth"
        data={{ wealth: 50000, wealth_description: "多年积蓄" }}
      />,
    );

    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/50000|50,000|多年积蓄|财富/)).not.toBeInTheDocument();
  });

  it("models player state, effects, and life review with three resources", () => {
    const player = {
      player_name: "小林",
      life_vision: "经营一家温暖的小店",
      energy: 70,
      mood: 60,
      knowledge: 50,
      age: 26,
      week: 0,
      current_round: 0,
      rounds_per_week: 3,
      character_settings: {},
    } satisfies PlayerState;
    const effects = { energy: -2, mood: 3, knowledge: 4 } satisfies EffectValues;
    const curves = {
      energy: [70, 68],
      mood: [60, 63],
      knowledge: [50, 54],
    } satisfies LifeReviewData["resource_curves"];

    // @ts-expect-error wealth is no longer a public player-state field
    expect(player.wealth).toBeUndefined();
    // @ts-expect-error wealth is no longer a public effect field
    expect(effects.wealth).toBeUndefined();
    // @ts-expect-error wealth is no longer a public life-review curve
    expect(curves.wealth).toBeUndefined();
  });
});
