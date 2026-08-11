import React from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  MobileActionDock,
  type MobileActionDockAction,
} from "@/components/story101/MobileActionDock";

describe("MobileActionDock", () => {
  it("renders up to four named native actions in one mobile safe-area dock", async () => {
    const user = userEvent.setup();
    const onSave = jest.fn();
    const actions: MobileActionDockAction[] = [
      { id: "save", label: "保存", icon: <span>存</span>, onSelect: onSave },
      { id: "history", label: "历史", icon: <span>史</span>, onSelect: jest.fn() },
      { id: "collection", label: "收集", icon: <span>集</span>, onSelect: jest.fn() },
      {
        id: "more",
        label: "更多",
        icon: <span>多</span>,
        onSelect: jest.fn(),
        controls: "play-tools-sheet",
        expanded: false,
      },
    ];

    render(<MobileActionDock actions={actions} />);

    const dock = screen.getByRole("navigation", { name: "游戏快捷工具" });
    expect(dock).toHaveAttribute("data-slot", "mobile-action-dock");
    expect(dock).toHaveClass("fixed", "bottom-0", "md:hidden", "safe-area-pb");
    expect(dock).not.toHaveClass("shadow-lg", "rounded-full");

    const buttons = within(dock).getAllByRole("button");
    expect(buttons).toHaveLength(4);
    for (const button of buttons) {
      expect(button).toHaveAttribute("type", "button");
      expect(button).toHaveClass("min-h-11", "min-w-11", "text-sm");
      expect(button).not.toHaveClass("text-xs");
      expect(button).not.toHaveClass("rounded-full");
    }

    const more = within(dock).getByRole("button", { name: "更多" });
    expect(more).toHaveAttribute("aria-controls", "play-tools-sheet");
    expect(more).toHaveAttribute("aria-expanded", "false");

    await user.click(within(dock).getByRole("button", { name: "保存" }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("preserves disabled action semantics", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();

    render(
      <MobileActionDock
        actions={[
          {
            id: "save",
            label: "保存",
            icon: <span>存</span>,
            onSelect,
            disabled: true,
          },
        ]}
      />,
    );

    const save = screen.getByRole("button", { name: "保存" });
    expect(save).toBeDisabled();
    await user.click(save);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("announces a busy action without changing its single-submit semantics", () => {
    render(
      <MobileActionDock
        actions={[
          {
            id: "save",
            label: "保存中",
            icon: <span>存</span>,
            onSelect: jest.fn(),
            disabled: true,
            busy: true,
          },
        ]}
      />,
    );

    const save = screen.getByRole("button", { name: "保存中" });
    expect(save).toBeDisabled();
    expect(save).toHaveAttribute("aria-busy", "true");
  });

  it("rejects a fifth action instead of silently hiding a real control", () => {
    const actions = Array.from({ length: 5 }, (_, index) => ({
      id: `action-${index}`,
      label: `动作 ${index}`,
      icon: <span>{index}</span>,
      onSelect: jest.fn(),
    }));

    expect(() => render(<MobileActionDock actions={actions} />)).toThrow(
      "MobileActionDock supports at most four actions",
    );
  });
});
