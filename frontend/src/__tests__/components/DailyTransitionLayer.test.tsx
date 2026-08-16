import { fireEvent, render, screen } from "@testing-library/react";

import { DailyTransitionLayer } from "@/components/game/DailyTransitionLayer";
import type { DailyGenerationCommandState } from "@/hooks/game/dailyGenerationCommand";


const running: DailyGenerationCommandState = {
  status: "running",
  mode: "generate_missing",
  operationId: "op-1",
  attempt: 2,
  maxAttempts: 3,
  failure: null,
};


describe("DailyTransitionLayer", () => {
  it("renders narrative copy, exact next date, and reduced-motion-safe styling", () => {
    const { container } = render(
      <DailyTransitionLayer
        transitionText="这一念被妥善收下，明日的门扉正缓缓开启。"
        nextDate="2026-08-14"
        generation={running}
        onRetry={jest.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "这一念被妥善收下，明日的门扉正缓缓开启。",
    );
    expect(screen.getByText("公元 2026 年 8 月 14 日")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("motion-reduce:transition-none");
    expect(screen.getByRole("button", { name: "正在生成" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("第 2/3 次")).toBeInTheDocument();
  });

  it("keeps the prose and offers an explicit retry after generation failure", () => {
    const retry = jest.fn();
    render(
      <DailyTransitionLayer
        transitionText="今日的回声渐远，明日已从静处缓缓靠近。"
        nextDate="2026-08-14"
        generation={{
          status: "failed",
          mode: "generate_missing",
          operationId: "op-failed",
          attempt: 3,
          maxAttempts: 3,
          failure: {
            message: "故事生成未能完成",
            summary: "故事生成未能完成",
            retryable: true,
          },
        }}
        onRetry={retry}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("故事生成未能完成");
    fireEvent.click(screen.getByRole("button", { name: "再次生成" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
