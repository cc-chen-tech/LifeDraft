import { render, screen } from "@testing-library/react";
import { OpeningCompletionGate } from "@/components/game/OpeningCompletionGate";

describe("OpeningCompletionGate", () => {
  it("keeps the completion gate visible without pulse animation while text catches up", () => {
    render(
      <OpeningCompletionGate
        backendComplete
        visibleComplete={false}
        onStart={jest.fn()}
      />
    );

    const status = screen.getByText("正在显示完整故事...");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).not.toHaveClass("animate-pulse");
    expect(screen.getByRole("button", { name: "开始我的人生" })).toBeDisabled();
  });

  it("uses a touch-sized non-submit action without replaying a word animation", () => {
    render(
      <OpeningCompletionGate
        backendComplete
        visibleComplete
        onStart={jest.fn()}
      />
    );

    const start = screen.getByRole("button", { name: "开始我的人生" });
    expect(start).toHaveAttribute("type", "button");
    expect(start).toHaveAttribute("data-size", "touch");
    expect(start).not.toHaveClass("animate-fade-in-word");
  });
});
