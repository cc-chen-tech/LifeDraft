import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  PlayTools,
  type PlayToolsProps,
} from "@/components/game/PlayTools";

function createProps(overrides: Partial<PlayToolsProps> = {}): PlayToolsProps {
  return {
    isSaving: false,
    isStoryBusy: false,
    isViewingHistory: false,
    constraintLevel: "expert",
    narrativeStyleId: "literary",
    narrativeStyles: [
      {
        style_id: "literary",
        style_name: "文学叙事",
        description: "重视语言与人物感受",
      },
      {
        style_id: "documentary",
        style_name: "纪实叙事",
        description: "重视事件与现实细节",
      },
    ],
    narrativeStylesLoading: false,
    rewriteDisabled: false,
    enableSceneImage: true,
    onSave: jest.fn(),
    onOpenHistory: jest.fn(),
    onOpenCollection: jest.fn(),
    onOpenChat: jest.fn(),
    onOpenRewrite: jest.fn(),
    onOpenSummary: jest.fn(),
    onRegenerate: jest.fn(),
    onOpenSound: jest.fn(),
    onHome: jest.fn(),
    onConstraintLevelChange: jest.fn(),
    onNarrativeStyleChange: jest.fn(),
    onSceneImageChange: jest.fn(),
    onRequestNarrativeStyles: jest.fn(),
    onOpenTools: jest.fn(),
    onToolsOpenChange: jest.fn(),
    ...overrides,
  };
}

describe("PlayTools", () => {
  it("offers one desktop tools trigger and four mobile shortcuts backed by one modal sheet", async () => {
    const user = userEvent.setup();
    const props = createProps();
    render(<PlayTools {...props} />);

    const desktopTrigger = screen.getByRole("button", { name: "打开工具" });
    expect(desktopTrigger).toHaveClass("hidden", "md:inline-flex", "min-h-11");

    const dock = screen.getByRole("navigation", { name: "游戏快捷工具" });
    expect(within(dock).getAllByRole("button")).toHaveLength(4);
    expect(within(dock).getByRole("button", { name: "保存" })).toBeInTheDocument();
    expect(within(dock).getByRole("button", { name: "历史" })).toBeInTheDocument();
    expect(within(dock).getByRole("button", { name: "收集" })).toBeInTheDocument();

    await user.click(within(dock).getByRole("button", { name: "保存" }));
    expect(props.onSave).toHaveBeenCalledTimes(1);

    await user.click(within(dock).getByRole("button", { name: "更多" }));
    const sheet = screen.getByRole("dialog", { name: "游戏工具" });
    expect(screen.getAllByRole("dialog", { name: "游戏工具" })).toHaveLength(1);
    expect(within(sheet).getByRole("button", { name: "保存游戏" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "打开历史回顾" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "打开收集" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "打开剧情助手" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "改写当前故事" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "生成人生总结" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "重新生成当前故事" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "打开声音" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "返回首页" })).toBeInTheDocument();
    expect(props.onRequestNarrativeStyles).not.toHaveBeenCalled();
  });

  it("shows the mobile save action as busy while preserving its disabled guard", () => {
    render(<PlayTools {...createProps({ isSaving: true })} />);

    const save = within(
      screen.getByRole("navigation", { name: "游戏快捷工具" }),
    ).getByRole("button", { name: "保存中" });
    expect(save).toBeDisabled();
    expect(save).toHaveAttribute("aria-busy", "true");
  });

  it("keeps the sound action disabled with a reason until playable context exists", async () => {
    const user = userEvent.setup();
    const props = { ...createProps(), soundAvailable: false };
    render(<PlayTools {...props} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    const sheet = screen.getByRole("dialog", { name: "游戏工具" });
    const soundAction = within(sheet).getByRole("button", { name: "打开声音" });

    expect(soundAction).toBeDisabled();
    expect(soundAction).toHaveAttribute(
      "aria-describedby",
      "play-sound-unavailable",
    );
    expect(within(sheet).getByText("故事声音准备好后可在这里打开")).toHaveAttribute(
      "id",
      "play-sound-unavailable",
    );
    await user.click(soundAction);
    expect(props.onOpenSound).not.toHaveBeenCalled();
    expect(sheet).toBeInTheDocument();
  });

  it("keeps quality, real narrative styles, and scene-image state controlled by props", async () => {
    const user = userEvent.setup();
    const props = createProps();
    render(<PlayTools {...props} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    const sheet = screen.getByRole("dialog", { name: "游戏工具" });

    expect(within(sheet).getByRole("radio", { name: "专家" })).toBeChecked();
    await user.click(within(sheet).getByRole("radio", { name: "大师" }));
    expect(props.onConstraintLevelChange).toHaveBeenCalledWith("master");

    await user.click(within(sheet).getByRole("button", { name: "叙事风格" }));
    expect(props.onRequestNarrativeStyles).toHaveBeenCalledTimes(1);
    expect(within(sheet).getByText("重视语言与人物感受")).toBeInTheDocument();
    expect(within(sheet).getByRole("radio", { name: /文学叙事/ })).toBeChecked();
    await user.click(within(sheet).getByRole("radio", { name: /纪实叙事/ }));
    expect(props.onNarrativeStyleChange).toHaveBeenCalledWith("documentary");

    const sceneImage = within(sheet).getByRole("checkbox", { name: "场景插画" });
    expect(sceneImage).toBeChecked();
    await user.click(sceneImage);
    expect(props.onSceneImageChange).toHaveBeenCalledWith(false);
  });

  it("loads narrative styles only when their disclosure is explicitly opened", async () => {
    const user = userEvent.setup();
    const props = createProps();
    render(<PlayTools {...props} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    expect(props.onRequestNarrativeStyles).not.toHaveBeenCalled();

    const disclosure = screen.getByRole("button", { name: "叙事风格" });
    expect(disclosure).toHaveAttribute("aria-expanded", "false");
    await user.click(disclosure);
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    expect(props.onRequestNarrativeStyles).toHaveBeenCalledTimes(1);
  });

  it("disables rewrite with the real unavailable reason", async () => {
    const user = userEvent.setup();
    render(
      <PlayTools
        {...createProps({
          rewriteDisabled: true,
          rewriteDisabledReason: "当前故事过长，无法改写",
        })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    const rewrite = screen.getByRole("button", { name: "改写当前故事" });
    expect(rewrite).toBeDisabled();
    const reasonId = rewrite.getAttribute("aria-describedby");
    expect(reasonId).toBeTruthy();
    expect(document.getElementById(reasonId!)).toHaveTextContent(
      "当前故事过长，无法改写",
    );
  });

  it("closes competing surfaces before opening the tools sheet", async () => {
    const user = userEvent.setup();
    const observed: boolean[] = [];
    const props = createProps({
      onOpenTools: jest.fn(() => {
        observed.push(
          Boolean(document.querySelector('[data-slot="sheet-content"][data-state="open"]')),
        );
      }),
    });
    render(<PlayTools {...props} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    expect(props.onOpenTools).toHaveBeenCalledTimes(1);
    expect(observed).toEqual([false]);
  });

  it("reports the modal surface lifetime so page feedback cannot overlap it", async () => {
    const user = userEvent.setup();
    const onToolsOpenChange = jest.fn();
    render(<PlayTools {...createProps({ onToolsOpenChange })} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    expect(onToolsOpenChange).toHaveBeenLastCalledWith(true);

    await user.click(screen.getByRole("button", { name: "关闭工具" }));
    expect(onToolsOpenChange).toHaveBeenLastCalledWith(false);
  });

  it("disables story tools while generation is busy or history is being viewed", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <PlayTools {...createProps({ isStoryBusy: true })} />,
    );

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    let sheet = screen.getByRole("dialog", { name: "游戏工具" });
    for (const name of [
      "打开剧情助手",
      "改写当前故事",
      "生成人生总结",
      "重新生成当前故事",
    ]) {
      expect(within(sheet).getByRole("button", { name })).toBeDisabled();
    }

    await user.click(within(sheet).getByRole("button", { name: "关闭工具" }));
    rerender(<PlayTools {...createProps({ isViewingHistory: true })} />);
    await user.click(screen.getByRole("button", { name: "打开工具" }));
    sheet = screen.getByRole("dialog", { name: "游戏工具" });
    expect(within(sheet).getByRole("button", { name: "改写当前故事" })).toBeDisabled();
    expect(within(sheet).getByRole("button", { name: "重新生成当前故事" })).toBeDisabled();
  });

  it("keeps save available while story generation is busy", async () => {
    const user = userEvent.setup();
    const props = createProps({ isStoryBusy: true });
    render(<PlayTools {...props} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    const sheet = screen.getByRole("dialog", { name: "游戏工具" });
    const save = within(sheet).getByRole("button", { name: "保存游戏" });

    expect(save).toBeEnabled();
    await user.click(save);
    expect(props.onSave).toHaveBeenCalledTimes(1);
  });

  it("closes the tools sheet before opening another panel", async () => {
    const user = userEvent.setup();
    const observedOpenState: {
      action: string;
      open: boolean;
      activeLabel: string | null;
    }[] = [];
    const observe = (action: string) =>
      jest.fn(() => {
        observedOpenState.push({
          action,
          open: Boolean(
            document.querySelector(
              '[data-slot="sheet-content"][data-state="open"]',
            ),
          ),
          activeLabel: document.activeElement?.textContent?.trim() ?? null,
        });
      });
    const props = createProps({
      onSave: observe("save"),
      onOpenHistory: observe("history"),
      onOpenCollection: observe("collection"),
      onOpenChat: observe("chat"),
      onOpenRewrite: observe("rewrite"),
      onOpenSummary: observe("summary"),
      onOpenSound: observe("sound"),
    });
    render(<PlayTools {...props} />);

    for (const [label, action] of [
      ["保存游戏", "save"],
      ["打开历史回顾", "history"],
      ["打开收集", "collection"],
      ["打开剧情助手", "chat"],
      ["改写当前故事", "rewrite"],
      ["生成人生总结", "summary"],
      ["打开声音", "sound"],
    ] as const) {
      await user.click(screen.getByRole("button", { name: "打开工具" }));
      await user.click(
        within(screen.getByRole("dialog", { name: "游戏工具" })).getByRole(
          "button",
          { name: label },
        ),
      );
      expect(observedOpenState.at(-1)).toEqual({
        action,
        open: false,
        activeLabel: "打开工具",
      });
    }

    expect(props.onSave).toHaveBeenCalledTimes(1);
    expect(props.onOpenHistory).toHaveBeenCalledTimes(1);
    expect(props.onOpenCollection).toHaveBeenCalledTimes(1);
    expect(props.onOpenChat).toHaveBeenCalledTimes(1);
    expect(props.onOpenRewrite).toHaveBeenCalledTimes(1);
    expect(props.onOpenSummary).toHaveBeenCalledTimes(1);
    expect(props.onOpenSound).toHaveBeenCalledTimes(1);
  });

  it("closes on busy or history transitions without reopening when they clear", async () => {
    const user = userEvent.setup();
    const props = createProps();
    const { rerender } = render(<PlayTools {...props} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    expect(screen.getByRole("dialog", { name: "游戏工具" })).toBeInTheDocument();

    rerender(<PlayTools {...props} isStoryBusy />);
    await waitFor(() => {
      expect(
        screen.queryByRole("dialog", { name: "游戏工具" }),
      ).not.toBeInTheDocument();
    });

    rerender(<PlayTools {...props} isStoryBusy={false} />);
    expect(
      screen.queryByRole("dialog", { name: "游戏工具" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开工具" }));
    rerender(<PlayTools {...props} isViewingHistory />);
    await waitFor(() => {
      expect(
        screen.queryByRole("dialog", { name: "游戏工具" }),
      ).not.toBeInTheDocument();
    });

    rerender(<PlayTools {...props} isViewingHistory={false} />);
    expect(
      screen.queryByRole("dialog", { name: "游戏工具" }),
    ).not.toBeInTheDocument();
  });

  it("layers the modal above the persistent sound control", async () => {
    const user = userEvent.setup();
    render(<PlayTools {...createProps()} />);

    await user.click(screen.getByRole("button", { name: "打开工具" }));

    expect(document.querySelector('[data-slot="sheet-overlay"]')).toHaveClass(
      "z-[60]",
    );
    expect(screen.getByRole("dialog", { name: "游戏工具" })).toHaveClass(
      "z-[61]",
    );
  });

  it("returns focus to the desktop or mobile trigger after Escape", async () => {
    const user = userEvent.setup();
    render(<PlayTools {...createProps()} />);

    const desktopTrigger = screen.getByRole("button", { name: "打开工具" });
    await user.click(desktopTrigger);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(desktopTrigger).toHaveFocus());

    const moreTrigger = within(
      screen.getByRole("navigation", { name: "游戏快捷工具" }),
    ).getByRole("button", { name: "更多" });
    await user.click(moreTrigger);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(moreTrigger).toHaveFocus());

    expect(
      screen.queryByRole("dialog", { name: "游戏工具" }),
    ).not.toBeInTheDocument();
  });
});
