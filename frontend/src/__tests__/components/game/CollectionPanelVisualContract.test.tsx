import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CollectionPanel } from "@/components/game/CollectionPanel";
import {
  CharacterList,
  ItemList,
  LandmarkList,
} from "@/components/game/collection";
import type {
  CharacterCollectionItem,
  ItemCollectionItem,
  LandmarkCollectionItem,
} from "@/lib/types";
import { useCollectionStore } from "@/stores/useCollectionStore";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

const character: CharacterCollectionItem = {
  name: "林舟",
  role: "旧友",
  can_delete: true,
  description: "",
  affinity: 100,
  age: null,
  gender: null,
  occupation: null,
  personality_traits: [],
  image_url: null,
  image_generated: false,
  description_generated: true,
};

const item: ItemCollectionItem = {
  name: "旧怀表",
  description: "祖父留下的旧物。",
  importance: "important",
  category: "keepsake",
  acquired_week: 2,
  acquired_context: "书房抽屉",
  is_key_item: true,
  image_url: null,
  image_generated: false,
  description_generated: true,
  metadata: {},
};

const landmark: LandmarkCollectionItem = {
  name: "旧码头",
  description: "雨夜会面的地点。",
  category: "area",
  importance: "normal",
  first_appear_week: 1,
  appear_count: 2,
  last_appear_week: 2,
  context: "雨夜会面地点",
  is_key_location: true,
  image_url: null,
  image_generated: false,
  metadata: {},
};

describe("CollectionPanel visual contract", () => {
  it("exposes separate detail and delete actions for removable directory rows", () => {
    const onDelete = jest.fn();
    render(
      <CharacterList
        characters={[
          { ...character, role: "主角", can_delete: false },
          { ...character, name: "陈晓雨", role: "同事" },
        ]}
        isLoading={false}
        onCharacterClick={() => undefined}
        onOpenDeleteConfirm={onDelete}
      />,
    );

    expect(screen.getByRole("button", { name: "查看人物：陈晓雨" })).toBeVisible();
    expect(screen.getByRole("button", { name: "删除人物陈晓雨" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "删除人物林舟" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除人物陈晓雨" })).toHaveClass("size-11");
  });

  it("keeps same-name entities in another category enabled and reports row categories", () => {
    const onItemDelete = jest.fn();
    const onLandmarkDelete = jest.fn();
    render(
      <>
        <ItemList
          items={[item]}
          isLoading={false}
          onItemClick={() => undefined}
          onOpenDeleteConfirm={onItemDelete}
          deletingEntity={{ type: "landmark", name: item.name }}
        />
        <LandmarkList
          landmarks={[{ ...landmark, name: item.name }]}
          isLoading={false}
          onLandmarkClick={() => undefined}
          onOpenDeleteConfirm={onLandmarkDelete}
        />
      </>,
    );
    const itemDelete = screen.getByRole("button", { name: `删除物品${item.name}` });
    expect(itemDelete).toBeEnabled();
    screen.getByRole("button", { name: `删除标志物${item.name}` }).click();
    expect(onLandmarkDelete).toHaveBeenCalledWith("landmark", item.name);
    itemDelete.click();
    expect(onItemDelete).toHaveBeenCalledWith("item", item.name);
  });

  it("keeps failed row deletion confirmation open with visible feedback", async () => {
    const user = userEvent.setup();
    useCollectionStore.setState({
      characters: [],
      items: [item],
      landmarks: [],
      activeTab: "items",
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      isLoading: false,
      isRefreshing: false,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: null,
      isRecognizing: false,
      recognizedEntities: null,
      isDeleting: false,
      deletingEntity: null,
      deleteItem: jest.fn(async () => {
        useCollectionStore.setState({ error: "删除失败" });
        return false;
      }),
    });
    render(<CollectionPanel gameId={0} />);
    await user.click(screen.getByRole("button", { name: `删除物品${item.name}` }));
    const dialog = screen.getByRole("dialog", { name: "确认删除" });
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    expect(screen.getByRole("dialog", { name: "确认删除" })).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("删除失败");
  });
  it("layers a real collection detail dialog above its parent play sheet", async () => {
    const user = userEvent.setup();
    useCollectionStore.setState({
      characters: [character],
      items: [],
      landmarks: [],
      isLoading: false,
      isRefreshing: false,
      activeTab: "characters",
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: null,
      isRecognizing: false,
      recognizedEntities: null,
      isDeleting: false,
      deletingEntity: null,
    });

    render(
      <Sheet open onOpenChange={() => undefined}>
        <SheetContent
          className="z-[70] w-full max-w-[min(100vw,34rem)] p-0"
          showCloseButton={false}
        >
          <SheetTitle>收集</SheetTitle>
          <CollectionPanel gameId={0} />
        </SheetContent>
      </Sheet>,
    );

    const directoryAction = screen.getByRole("button", { name: "查看人物：林舟" });
    await user.click(directoryAction);

    const detail = screen.getByRole("dialog", { name: "林舟" });
    const detailOverlay = document.querySelector('[data-slot="dialog-overlay"]');
    expect(detail).toHaveClass("z-[81]");
    expect(detailOverlay).toHaveClass("z-[80]");
    expect(detail).toBeVisible();
    const detailClose = screen.getByRole("button", { name: "关闭林舟人物详情" });
    expect(detailClose).toBeVisible();

    await user.click(detailClose);
    await waitFor(() => expect(directoryAction).toHaveFocus());

    await user.click(directoryAction);
    const deleteAction = screen.getByRole("button", { name: "删除人物林舟" });
    await user.click(deleteAction);
    const deleteDialog = screen.getByRole("dialog", { name: "确认删除" });
    expect(deleteDialog).toHaveClass("z-[91]");
    expect(document.querySelectorAll('[data-slot="dialog-overlay"]')[1]).toHaveClass(
      "z-[90]",
    );

    await user.click(within(deleteDialog).getByRole("button", { name: "取消" }));
    await waitFor(() => expect(deleteAction).toHaveFocus());
  });

  it("returns focus to the active directory tab after a successful delete removes the row", async () => {
    const user = userEvent.setup();
    const store = useCollectionStore.getState() as unknown as Record<
      string,
      unknown
    >;
    const originalDeleteCharacter = store.deleteCharacter;
    store.deleteCharacter = jest.fn(async () => {
      useCollectionStore.setState({
        characters: [],
        selectedCharacter: null,
      });
      return true;
    });
    useCollectionStore.setState({
      characters: [character],
      items: [],
      landmarks: [],
      isLoading: false,
      isRefreshing: false,
      activeTab: "characters",
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: null,
      isRecognizing: false,
      recognizedEntities: null,
      isDeleting: false,
      deletingEntity: null,
    });

    try {
      render(<CollectionPanel gameId={0} />);
      const directoryAction = screen.getByRole("button", {
        name: "查看人物：林舟",
      });
      await user.click(directoryAction);
      await user.click(screen.getByRole("button", { name: "删除人物林舟" }));
      await user.click(
        within(screen.getByRole("dialog", { name: "确认删除" })).getByRole(
          "button",
          { name: "删除" },
        ),
      );

      await waitFor(() =>
        expect(
          screen.getByRole("tab", { name: "人物 (0)" }),
        ).toHaveFocus(),
      );
    } finally {
      store.deleteCharacter = originalDeleteCharacter;
    }
  });

  it("keeps the first level width-safe with semantic 44px tabs, actions, and error feedback", () => {
    useCollectionStore.setState({
      characters: [character],
      items: [item],
      landmarks: [landmark],
      isLoading: false,
      isRefreshing: false,
      activeTab: "items",
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: "图片生成额度暂时不可用",
      isRecognizing: false,
      recognizedEntities: null,
      isDeleting: false,
      deletingEntity: null,
    });

    const { container } = render(<CollectionPanel gameId={0} />);
    const panel = container.querySelector('[data-slot="collection-panel"]');

    expect(panel).toHaveClass(
      "w-full",
      "min-w-0",
      "max-w-full",
      "overflow-x-hidden",
    );
    expect(panel?.className).not.toContain("w-[400px]");

    const tabs = screen.getByRole("tablist", { name: "收集分类" });
    for (const tab of within(tabs).getAllByRole("tab")) {
      expect(tab).toHaveClass("min-h-11", "min-w-11", "rounded-none");
      expect(tab).not.toHaveClass("shadow-xs");
      expect(tab).toHaveAttribute("aria-selected");
    }

    for (const name of ["添加物品", "智能识别", "关闭收集错误"]) {
      const button = screen.getByRole("button", { name });
      expect(button).toHaveClass("min-h-11", "min-w-11");
      expect(button).not.toHaveClass("shadow-xs");
    }

    const commandStrip = screen.getByRole("group", { name: "收集操作" });
    expect(commandStrip).toHaveClass("flex", "items-stretch", "border-b");
    expect(commandStrip).not.toHaveClass("grid-cols-1");
    expect(commandStrip.firstElementChild).toHaveTextContent("添加物品");

    const alert = screen.getByRole("alert");
    expect(alert.closest('[data-slot="feedback-notice"]')).not.toBeNull();
  });

  it("returns focus to the contextual add action when its dialog closes", async () => {
    const user = userEvent.setup();
    useCollectionStore.setState({
      characters: [character],
      items: [],
      landmarks: [],
      isLoading: false,
      isRefreshing: false,
      activeTab: "characters",
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: null,
      isRecognizing: false,
      recognizedEntities: null,
      isDeleting: false,
      deletingEntity: null,
    });

    render(<CollectionPanel gameId={0} />);
    const addAction = screen.getByRole("button", { name: "添加人物" });
    await user.click(addAction);
    await user.click(within(screen.getByRole("dialog", { name: "添加人物" })).getByRole("button", { name: "取消" }));

    await waitFor(() => expect(addAction).toHaveFocus());
  });

  it("keeps all three landmark commands accessible in a compact narrow strip", () => {
    useCollectionStore.setState({
      characters: [],
      items: [],
      landmarks: [landmark],
      isLoading: false,
      isRefreshing: false,
      activeTab: "landmarks",
      selectedCharacter: null,
      selectedItem: null,
      selectedLandmark: null,
      generatingImageFor: null,
      generatingDescriptionFor: null,
      regeneratingImageFor: null,
      error: null,
      isRecognizing: false,
      recognizedEntities: null,
      isDeleting: false,
      deletingEntity: null,
    });

    render(<CollectionPanel gameId={0} />);
    const commandStrip = screen.getByRole("group", { name: "收集操作" });
    const batchAction = within(commandStrip).getByRole("button", {
      name: "批量生成图片",
    });

    for (const name of ["添加标志物", "智能识别", "批量生成图片"]) {
      expect(within(commandStrip).getByRole("button", { name })).toHaveClass(
        "min-h-11",
        "min-w-11",
      );
    }
    expect(batchAction).toHaveAttribute("aria-label", "批量生成图片");
    expect(batchAction).toHaveClass("shrink-0", "px-3", "sm:px-4");
    expect(within(batchAction).getByText("批量生成图片")).toHaveClass(
      "sr-only",
      "sm:not-sr-only",
    );
  });

  it.each([
    {
      directoryName: "人物目录",
      actionName: "查看人物：林舟",
      renderDirectory: () =>
        render(
          <CharacterList
            characters={[character]}
            isLoading={false}
            onCharacterClick={() => undefined}
          />,
        ),
    },
    {
      directoryName: "物品目录",
      actionName: "查看物品：旧怀表",
      renderDirectory: () =>
        render(
          <ItemList
            items={[item]}
            isLoading={false}
            onItemClick={() => undefined}
          />,
        ),
    },
    {
      directoryName: "标志物目录",
      actionName: "查看标志物：旧码头",
      renderDirectory: () =>
        render(
          <LandmarkList
            landmarks={[landmark]}
            isLoading={false}
            onLandmarkClick={() => undefined}
          />,
        ),
    },
  ])(
    "renders $directoryName as one width-safe divider directory instead of cards",
    ({ directoryName, actionName, renderDirectory }) => {
      renderDirectory();

      const directory = screen.getByRole("list", { name: directoryName });
      expect(directory).toHaveClass("w-full", "min-w-0", "divide-y");
      expect(directory).not.toHaveClass("grid-cols-2", "gap-3");
      expect(directory.querySelector('[data-slot="badge"]')).toBeNull();

      const row = screen.getByRole("button", { name: actionName });
      expect(row).toHaveAttribute("type", "button");
      expect(row).toHaveClass("min-h-11", "w-full", "min-w-0", "rounded-none");
      expect(row).not.toHaveClass("bg-card", "rounded-lg", "shadow-lg");
    },
  );
});
