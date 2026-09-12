"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FeedbackNotice } from "@/components/story101";
import { Package, Wand2, Loader2, Plus, Image as ImageIcon } from "lucide-react";
import { useCollectionStore } from "@/stores/useCollectionStore";
import type { CharacterCollectionItem, ItemCollectionItem, LandmarkCollectionItem, RecognizedEntity } from "@/lib/types";

// 导入子组件
import {
  CollectionTabs,
  CharacterList,
  ItemList,
  LandmarkList,
  CharacterDetail,
  ItemDetail,
  LandmarkDetail,
  RecognizeDialog,
  AddEntityDialog,
  DeleteConfirmDialog,
  type CollectionTab,
  type RegenerateType,
  type EntityToDelete,
} from "./collection";

interface CollectionPanelProps {
  gameId: number;
}

/**
 * 收集面板组件 - 管理人物、物品和标志物的收集展示
 * 这是一个容器组件，组织和协调各个子组件
 */
export function CollectionPanel({ gameId }: CollectionPanelProps) {
  const {
    characters,
    items,
    landmarks,
    isLoading,
    isRefreshing,
    activeTab,
    selectedCharacter,
    selectedItem,
    selectedLandmark,
    generatingImageFor,
    generatingDescriptionFor,
    regeneratingImageFor,
    error,
    isRecognizing,
    recognizedEntities,
    isDeleting,
    deletingEntity,
    fetchCollection,
    setActiveTab,
    selectCharacter,
    selectItem,
    selectLandmark,
    generateCharacterImage,
    generateItemImage,
    generateLandmarkImage,
    batchGenerateLandmarkImages,
    generateItemDescription,
    generateLandmarkDescription,
    regenerateCharacterImage,
    regenerateItemImage,
    recognizeEntities,
    addRecognizedEntities,
    autoCollectRecognizedEntities,
    clearRecognizedEntities,
    createCharacter,
    createItem,
    createLandmark,
    deleteItem,
    deleteCharacter,
    deleteLandmark,
    clearError,
  } = useCollectionStore();

  // 修改图片相关状态
  const [showRegenerateInput, setShowRegenerateInput] = useState(false);
  const [regenerateFeedback, setRegenerateFeedback] = useState("");
  const [regenerateType, setRegenerateType] = useState<RegenerateType>(null);

  // 识别相关状态
  const [showRecognizeDialog, setShowRecognizeDialog] = useState(false);
  const [selectedRecognizedItems, setSelectedRecognizedItems] = useState<RecognizedEntity[]>([]);
  const [selectedRecognizedCharacters, setSelectedRecognizedCharacters] = useState<RecognizedEntity[]>([]);
  const [selectedRecognizedLandmarks, setSelectedRecognizedLandmarks] = useState<RecognizedEntity[]>([]);

  // 手动添加相关状态
  const [showAddEntityDialog, setShowAddEntityDialog] = useState(false);
  const [newEntityName, setNewEntityName] = useState("");
  const [generateDescriptionForNewEntity, setGenerateDescriptionForNewEntity] = useState(true);

  // 删除确认相关状态
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [entityToDelete, setEntityToDelete] = useState<EntityToDelete | null>(null);
  const [isInitialSyncing, setIsInitialSyncing] = useState(false);
  const detailReturnFocusRef = useRef<HTMLElement | null>(null);
  const recognizeReturnFocusRef = useRef<HTMLElement | null>(null);
  const addEntityReturnFocusRef = useRef<HTMLElement | null>(null);
  const deleteReturnFocusRef = useRef<HTMLElement | null>(null);

  const rememberDialogOpener = (targetRef: { current: HTMLElement | null }) => {
    targetRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  };

  const restoreDialogOpener = (targetRef: { current: HTMLElement | null }) => (event: Event) => {
    event.preventDefault();
    const target = targetRef.current;
    targetRef.current = null;
    if (target?.isConnected) {
      target.focus();
    }
  };

  const restoreDeleteDialogOpener = (event: Event) => {
    event.preventDefault();
    const target = deleteReturnFocusRef.current;
    deleteReturnFocusRef.current = null;
    const fallbackTarget = document.getElementById(
      `collection-tab-${activeTab}`,
    );
    if (target?.isConnected) {
      target.focus();
    } else if (fallbackTarget instanceof HTMLElement) {
      fallbackTarget.focus();
    }
  };

  // 初始加载
  useLayoutEffect(() => {
    let cancelled = false;

    if (!gameId) return;

    setIsInitialSyncing(true);
    void (async () => {
      await fetchCollection(gameId);

      const state = useCollectionStore.getState();
      const needsInitialRecognition =
        state.characters.length <= 1 ||
        (state.items.length === 0 && state.landmarks.length === 0);
      if (needsInitialRecognition) {
        await autoCollectRecognizedEntities(gameId);
      }

      if (!cancelled) {
        setIsInitialSyncing(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- zustand action 引用稳定，仅在 gameId 变化时重新获取
  }, [gameId]);

  // ==================== 点击处理函数 ====================

  const handleCharacterClick = (character: CharacterCollectionItem) => {
    rememberDialogOpener(detailReturnFocusRef);
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
    selectCharacter(character);
  };

  const handleItemClick = (item: ItemCollectionItem) => {
    rememberDialogOpener(detailReturnFocusRef);
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
    selectItem(item);
  };

  const handleLandmarkClick = (landmark: LandmarkCollectionItem) => {
    rememberDialogOpener(detailReturnFocusRef);
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
    selectLandmark(landmark);
  };

  const handleCloseDetail = () => {
    selectCharacter(null);
    selectItem(null);
    selectLandmark(null);
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  // ==================== 生成处理函数 ====================

  const handleGenerateCharacterImage = async (name: string) => {
    await generateCharacterImage(gameId, name);
  };

  const handleGenerateItemImage = async (itemName: string) => {
    await generateItemImage(gameId, itemName);
  };

  const handleGenerateItemDescription = async (itemName: string) => {
    await generateItemDescription(gameId, itemName);
  };

  const handleGenerateLandmarkImage = async (landmarkName: string) => {
    await generateLandmarkImage(gameId, landmarkName);
  };

  const handleBatchGenerateLandmarkImages = async () => {
    await batchGenerateLandmarkImages(gameId);
  };

  const handleGenerateLandmarkDescription = async (landmarkName: string) => {
    await generateLandmarkDescription(gameId, landmarkName);
  };

  // ==================== 修改处理函数 ====================

  const handleStartRegenerateCharacter = () => {
    setRegenerateType("character");
    setShowRegenerateInput(true);
    setRegenerateFeedback("");
  };

  const handleStartRegenerateItem = () => {
    setRegenerateType("item");
    setShowRegenerateInput(true);
    setRegenerateFeedback("");
  };

  const handleCancelRegenerate = () => {
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  const handleSubmitRegenerateCharacter = async () => {
    if (!selectedCharacter || !regenerateFeedback.trim()) return;
    await regenerateCharacterImage(gameId, selectedCharacter.name, regenerateFeedback.trim());
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  const handleSubmitRegenerateItem = async () => {
    if (!selectedItem || !regenerateFeedback.trim()) return;
    await regenerateItemImage(gameId, selectedItem.name, regenerateFeedback.trim());
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  // ==================== 识别处理函数 ====================

  const handleOpenRecognize = async () => {
    rememberDialogOpener(recognizeReturnFocusRef);
    setShowRecognizeDialog(true);
    const result = await recognizeEntities(gameId);
    if (result) {
      setSelectedRecognizedItems(result.items || []);
      setSelectedRecognizedCharacters(result.characters || []);
      setSelectedRecognizedLandmarks(result.landmarks || []);
    }
  };

  const handleCloseRecognize = () => {
    setShowRecognizeDialog(false);
    clearRecognizedEntities();
    setSelectedRecognizedItems([]);
    setSelectedRecognizedCharacters([]);
    setSelectedRecognizedLandmarks([]);
  };

  const handleSubmitRecognizedEntities = async () => {
    await addRecognizedEntities(gameId, {
      items: selectedRecognizedItems,
      characters: selectedRecognizedCharacters,
      landmarks: selectedRecognizedLandmarks,
    });
    setShowRecognizeDialog(false);
    setSelectedRecognizedItems([]);
    setSelectedRecognizedCharacters([]);
    setSelectedRecognizedLandmarks([]);
  };

  const toggleItemSelection = (item: RecognizedEntity) => {
    setSelectedRecognizedItems((prev) =>
      prev.some((i) => i.name === item.name)
        ? prev.filter((i) => i.name !== item.name)
        : [...prev, item]
    );
  };

  const toggleCharacterSelection = (character: RecognizedEntity) => {
    setSelectedRecognizedCharacters((prev) =>
      prev.some((c) => c.name === character.name)
        ? prev.filter((c) => c.name !== character.name)
        : [...prev, character]
    );
  };

  const toggleLandmarkSelection = (landmark: RecognizedEntity) => {
    setSelectedRecognizedLandmarks((prev) =>
      prev.some((l) => l.name === landmark.name)
        ? prev.filter((l) => l.name !== landmark.name)
        : [...prev, landmark]
    );
  };

  // ==================== 手动添加处理函数 ====================

  const handleOpenAddEntity = () => {
    rememberDialogOpener(addEntityReturnFocusRef);
    clearError();
    setShowAddEntityDialog(true);
    setNewEntityName("");
    setGenerateDescriptionForNewEntity(true);
  };

  const handleCloseAddEntity = () => {
    setShowAddEntityDialog(false);
    setNewEntityName("");
    clearError();
  };

  const handleSubmitAddEntity = async () => {
    const name = newEntityName.trim();
    if (!name) return;

    let created = false;
    switch (activeTab as CollectionTab) {
      case "characters":
        created = await createCharacter(gameId, name);
        break;
      case "items":
        created = await createItem(gameId, name, generateDescriptionForNewEntity);
        break;
      case "landmarks":
        created = await createLandmark(gameId, name);
        break;
    }

    if (created) {
      setShowAddEntityDialog(false);
      setNewEntityName("");
    }
  };

  // ==================== 删除处理函数 ====================

  const handleOpenDeleteConfirm = (type: "character" | "item" | "landmark", name: string) => {
    rememberDialogOpener(deleteReturnFocusRef);
    clearError();
    setEntityToDelete({ type, name });
    setShowDeleteConfirm(true);
  };

  const handleCloseDeleteConfirm = () => {
    setShowDeleteConfirm(false);
    setEntityToDelete(null);
    clearError();
  };

  const handleConfirmDelete = async () => {
    if (!entityToDelete) return;

    let deleted = false;
    switch (entityToDelete.type) {
      case "character":
        deleted = await deleteCharacter(gameId, entityToDelete.name);
        break;
      case "item":
        deleted = await deleteItem(gameId, entityToDelete.name);
        break;
      case "landmark":
        deleted = await deleteLandmark(gameId, entityToDelete.name);
        break;
    }

    if (deleted) {
      setShowDeleteConfirm(false);
      setEntityToDelete(null);
    }
  };

  return (
    <div
      className="flex h-full w-full min-w-0 max-w-full flex-col overflow-x-hidden overflow-y-hidden"
      data-slot="collection-panel"
    >
      {/* 标题 */}
      <div className="p-4 border-b flex-shrink-0">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Package className="w-5 h-5" />
          收集
        </h2>
        <p className="text-sm text-muted-foreground">
          {isInitialSyncing || isRefreshing ? "正在刷新，已加载内容保持可见" : "人物、物品和标志物收集记录"}
        </p>
      </div>

      {/* Tab 按钮 */}
      <CollectionTabs
        activeTab={activeTab as CollectionTab}
        onTabChange={setActiveTab}
        charactersCount={characters.length}
        itemsCount={items.length}
        landmarksCount={landmarks.length}
      />

      {/* 操作按钮 */}
      <div
        role="group"
        aria-label="收集操作"
        className="flex flex-shrink-0 items-stretch border-b border-[var(--border-default)]"
      >
        <Button
          type="button"
          size="touch"
          onClick={handleOpenAddEntity}
          className="min-w-11 flex-1 justify-start rounded-none px-4"
        >
          <Plus className="mr-1 size-4" />
          {activeTab === "characters" ? "添加人物" : activeTab === "items" ? "添加物品" : "添加标志物"}
        </Button>
        <Button
          type="button"
          variant="quiet"
          size="touch"
          onClick={handleOpenRecognize}
          disabled={isRecognizing}
          className="justify-center rounded-none border-l border-[var(--border-default)] px-4"
        >
          {isRecognizing ? (
            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
          ) : (
            <Wand2 className="w-4 h-4 mr-1" />
          )}
          智能识别
        </Button>
        {activeTab === "landmarks" && landmarks.some((l) => !l.image_generated) && (
          <Button
            type="button"
            variant="quiet"
            size="touch"
            onClick={handleBatchGenerateLandmarkImages}
            disabled={!!generatingImageFor}
            aria-label="批量生成图片"
            className="shrink-0 justify-center rounded-none border-l border-[var(--border-default)] px-3 sm:px-4"
          >
            {generatingImageFor ? (
              <Loader2 className="size-4 animate-spin sm:mr-1" />
            ) : (
              <ImageIcon className="size-4 sm:mr-1" />
            )}
            <span className="sr-only sm:not-sr-only">批量生成图片</span>
          </Button>
        )}
      </div>

      {/* 可滚动的内容区域 */}
      <ScrollArea className="min-h-0 min-w-0 flex-1">
        <div
          id={`collection-panel-${activeTab}`}
          role="tabpanel"
          aria-labelledby={`collection-tab-${activeTab}`}
          className="min-w-0 p-4"
        >
          {activeTab === "characters" && (
            <CharacterList
              characters={characters}
              isLoading={isLoading}
              onCharacterClick={handleCharacterClick}
              onOpenDeleteConfirm={handleOpenDeleteConfirm}
              deletingEntity={deletingEntity}
            />
          )}

          {activeTab === "items" && (
            <ItemList
              items={items}
              isLoading={isLoading}
              onItemClick={handleItemClick}
              onOpenDeleteConfirm={handleOpenDeleteConfirm}
              deletingEntity={deletingEntity}
            />
          )}

          {activeTab === "landmarks" && (
            <LandmarkList
              landmarks={landmarks}
              isLoading={isLoading}
              onLandmarkClick={handleLandmarkClick}
              onOpenDeleteConfirm={handleOpenDeleteConfirm}
              deletingEntity={deletingEntity}
            />
          )}
        </div>
      </ScrollArea>

      {/* 人物详情弹窗 */}
      <CharacterDetail
        character={selectedCharacter}
        onClose={handleCloseDetail}
        onCloseAutoFocus={restoreDialogOpener(detailReturnFocusRef)}
        onGenerateImage={handleGenerateCharacterImage}
        onStartRegenerate={handleStartRegenerateCharacter}
        onCancelRegenerate={handleCancelRegenerate}
        onSubmitRegenerate={handleSubmitRegenerateCharacter}
        onOpenDeleteConfirm={(name) => handleOpenDeleteConfirm("character", name)}
        generatingImageFor={generatingImageFor}
        regeneratingImageFor={regeneratingImageFor}
        showRegenerateInput={showRegenerateInput}
        regenerateType={regenerateType}
        regenerateFeedback={regenerateFeedback}
        onRegenerateFeedbackChange={setRegenerateFeedback}
        isDeleting={isDeleting}
      />

      {/* 物品详情弹窗 */}
      <ItemDetail
        item={selectedItem}
        onClose={handleCloseDetail}
        onCloseAutoFocus={restoreDialogOpener(detailReturnFocusRef)}
        onGenerateImage={handleGenerateItemImage}
        onGenerateDescription={handleGenerateItemDescription}
        onStartRegenerate={handleStartRegenerateItem}
        onCancelRegenerate={handleCancelRegenerate}
        onSubmitRegenerate={handleSubmitRegenerateItem}
        onOpenDeleteConfirm={(name) => handleOpenDeleteConfirm("item", name)}
        generatingImageFor={generatingImageFor}
        generatingDescriptionFor={generatingDescriptionFor}
        regeneratingImageFor={regeneratingImageFor}
        showRegenerateInput={showRegenerateInput}
        regenerateType={regenerateType}
        regenerateFeedback={regenerateFeedback}
        onRegenerateFeedbackChange={setRegenerateFeedback}
        isDeleting={isDeleting}
      />

      {/* 标志物详情弹窗 */}
      <LandmarkDetail
        landmark={selectedLandmark}
        onClose={handleCloseDetail}
        onCloseAutoFocus={restoreDialogOpener(detailReturnFocusRef)}
        onGenerateImage={handleGenerateLandmarkImage}
        onGenerateDescription={handleGenerateLandmarkDescription}
        onOpenDeleteConfirm={(name) => handleOpenDeleteConfirm("landmark", name)}
        generatingImageFor={generatingImageFor}
        generatingDescriptionFor={generatingDescriptionFor}
        isDeleting={isDeleting}
      />

      {/* 错误提示 */}
      {error && !showAddEntityDialog && (
        <div className="flex-shrink-0 border-t border-[var(--border-default)] p-4">
          <FeedbackNotice
            tone="danger"
            action={
              <Button
                type="button"
                variant="quiet"
                size="touch"
                className="w-full justify-start rounded-none border-t border-[var(--danger-border)] px-0"
                aria-label="关闭收集错误"
                onClick={clearError}
              >
                关闭
              </Button>
            }
          >
            {error}
          </FeedbackNotice>
        </div>
      )}

      {/* 智能识别对话框 */}
      <RecognizeDialog
        open={showRecognizeDialog}
        onClose={handleCloseRecognize}
        onCloseAutoFocus={restoreDialogOpener(recognizeReturnFocusRef)}
        onSubmit={handleSubmitRecognizedEntities}
        isRecognizing={isRecognizing}
        isLoading={isLoading}
        recognizedEntities={recognizedEntities}
        selectedItems={selectedRecognizedItems}
        selectedCharacters={selectedRecognizedCharacters}
        selectedLandmarks={selectedRecognizedLandmarks}
        onToggleItemSelection={toggleItemSelection}
        onToggleCharacterSelection={toggleCharacterSelection}
        onToggleLandmarkSelection={toggleLandmarkSelection}
      />

      {/* 手动添加实体对话框 */}
      <AddEntityDialog
        activeTab={activeTab as CollectionTab}
        open={showAddEntityDialog}
        onClose={handleCloseAddEntity}
        onCloseAutoFocus={restoreDialogOpener(addEntityReturnFocusRef)}
        onSubmit={handleSubmitAddEntity}
        entityName={newEntityName}
        onEntityNameChange={setNewEntityName}
        generateDescription={generateDescriptionForNewEntity}
        onGenerateDescriptionChange={setGenerateDescriptionForNewEntity}
        error={error}
        isLoading={isLoading}
      />

      {/* 删除确认对话框 */}
      <DeleteConfirmDialog
        open={showDeleteConfirm}
        onClose={handleCloseDeleteConfirm}
        onCloseAutoFocus={restoreDeleteDialogOpener}
        onConfirm={handleConfirmDelete}
        entityToDelete={entityToDelete}
        isDeleting={isDeleting}
        error={error}
      />
    </div>
  );
}
