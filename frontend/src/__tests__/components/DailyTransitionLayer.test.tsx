import { fireEvent, render, screen } from "@testing-library/react";

import { DailyTransitionLayer } from "@/components/game/DailyTransitionLayer";


describe("DailyTransitionLayer", () => {
  it("renders narrative copy, exact next date, and reduced-motion-safe styling", () => {
    const { container } = render(
      <DailyTransitionLayer
        transitionText="这一念被妥善收下，明日的门扉正缓缓开启。"
        nextDate="2026-08-14"
        failed={false}
        onRetry={jest.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "这一念被妥善收下，明日的门扉正缓缓开启。",
    );
    expect(screen.getByText("公元 2026 年 8 月 14 日")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("motion-reduce:transition-none");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("keeps the prose and offers an explicit retry after generation failure", () => {
    const retry = jest.fn();
    render(
      <DailyTransitionLayer
        transitionText="今日的回声渐远，明日已从静处缓缓靠近。"
        nextDate="2026-08-14"
        failed
        onRetry={retry}
      />,
    );

    expect(screen.getByText("下一日故事暂未生成")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试生成" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
