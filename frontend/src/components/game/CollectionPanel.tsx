"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  User,
  Package,
  MapPin,
  Image as ImageIcon,
  FileText,
  Sparkles,
  Loader2,
  Pencil,
  X,
  Wand2,
  Plus,
  Trash2,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCollectionStore } from "@/stores/useCollectionStore";
import type { CharacterCollectionItem, ItemCollectionItem, LandmarkCollectionItem, RecognizedEntity } from "@/lib/types";

interface CollectionPanelProps {
  gameId: number;
}

// 物品类别标签
const CATEGORY_LABELS: Record<string, string> = {
  weapon: "武器",
  tool: "工具",
  keepsake: "纪念品",
  treasure: "宝物",
  document: "文件",
  other: "其他",
};

// 标志物类别标签
const LANDMARK_CATEGORY_LABELS: Record<string, string> = {
  building: "建筑",
  nature: "自然景观",
  room: "房间",
  area: "区域",
  other: "其他",
};

// 重要程度标签
const IMPORTANCE_LABELS: Record<string, { label: string; color: string }> = {
  critical: { label: "关键", color: "bg-red-500" },
  important: { label: "重要", color: "bg-amber-500" },
  normal: { label: "普通", color: "bg-gray-400" },
};

export function CollectionPanel({ gameId }: CollectionPanelProps) {
  const {
    characters,
    items,
    landmarks,
    isLoading,
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
    generateItemDescription,
    generateLandmarkDescription,
    regenerateCharacterImage,
    regenerateItemImage,
    recognizeEntities,
    addRecognizedEntities,
    clearRecognizedEntities,
    createItem,
    deleteItem,
    deleteCharacter,
    deleteLandmark,
    clearError,
  } = useCollectionStore();

  // 修改图片相关状态
  const [showRegenerateInput, setShowRegenerateInput] = useState(false);
  const [regenerateFeedback, setRegenerateFeedback] = useState("");
  const [regenerateType, setRegenerateType] = useState<"character" | "item" | null>(null);

  // 识别相关状态
  const [showRecognizeDialog, setShowRecognizeDialog] = useState(false);
  const [selectedRecognizedItems, setSelectedRecognizedItems] = useState<RecognizedEntity[]>([]);
  const [selectedRecognizedCharacters, setSelectedRecognizedCharacters] = useState<RecognizedEntity[]>([]);
  const [selectedRecognizedLandmarks, setSelectedRecognizedLandmarks] = useState<RecognizedEntity[]>([]);

  // 手动添加相关状态
  const [showAddItemDialog, setShowAddItemDialog] = useState(false);
  const [newItemName, setNewItemName] = useState("");
  const [generateDescForNewItem, setGenerateDescForNewItem] = useState(true);

  // 删除确认相关状态
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [entityToDelete, setEntityToDelete] = useState<{ type: "character" | "item" | "landmark"; name: string } | null>(null);

  // 初始加载
  useEffect(() => {
    if (gameId) {
      fetchCollection(gameId);
    }
  }, [gameId, fetchCollection]);

  // 处理人物点击
  const handleCharacterClick = (character: CharacterCollectionItem) => {
    // 重置修改状态
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
    selectCharacter(character);
  };

  // 处理物品点击
  const handleItemClick = (item: ItemCollectionItem) => {
    // 重置修改状态
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
    selectItem(item);
  };

  // 处理标志物点击
  const handleLandmarkClick = (landmark: LandmarkCollectionItem) => {
    // 重置修改状态
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
    selectLandmark(landmark);
  };

  // 关闭详情弹窗
  const handleCloseDetail = () => {
    selectCharacter(null);
    selectItem(null);
    selectLandmark(null);
    // 重置修改状态
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  // 生成人物图片
  const handleGenerateCharacterImage = async (name: string) => {
    await generateCharacterImage(gameId, name);
  };

  // 生成物品图片
  const handleGenerateItemImage = async (itemName: string) => {
    await generateItemImage(gameId, itemName);
  };

  // 生成物品描述
  const handleGenerateItemDescription = async (itemName: string) => {
    await generateItemDescription(gameId, itemName);
  };

  // 生成标志物图片
  const handleGenerateLandmarkImage = async (landmarkName: string) => {
    await generateLandmarkImage(gameId, landmarkName);
  };

  // 生成标志物描述
  const handleGenerateLandmarkDescription = async (landmarkName: string) => {
    await generateLandmarkDescription(gameId, landmarkName);
  };

  // 开始修改人物画像
  const handleStartRegenerateCharacter = () => {
    setRegenerateType("character");
    setShowRegenerateInput(true);
    setRegenerateFeedback("");
  };

  // 开始修改物品图片
  const handleStartRegenerateItem = () => {
    setRegenerateType("item");
    setShowRegenerateInput(true);
    setRegenerateFeedback("");
  };

  // 取消修改
  const handleCancelRegenerate = () => {
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  // 提交修改人物画像
  const handleSubmitRegenerateCharacter = async () => {
    if (!selectedCharacter || !regenerateFeedback.trim()) return;

    await regenerateCharacterImage(gameId, selectedCharacter.name, regenerateFeedback.trim());
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  // 提交修改物品图片
  const handleSubmitRegenerateItem = async () => {
    if (!selectedItem || !regenerateFeedback.trim()) return;

    await regenerateItemImage(gameId, selectedItem.name, regenerateFeedback.trim());
    setShowRegenerateInput(false);
    setRegenerateFeedback("");
    setRegenerateType(null);
  };

  // ==================== 识别相关处理函数 ====================

  // 打开识别对话框
  const handleOpenRecognize = async () => {
    setShowRecognizeDialog(true);
    const result = await recognizeEntities(gameId, 3);
    if (result) {
      // 默认全选
      setSelectedRecognizedItems(result.items || []);
      setSelectedRecognizedCharacters(result.characters || []);
      setSelectedRecognizedLandmarks(result.landmarks || []);
    }
  };

  // 关闭识别对话框
  const handleCloseRecognize = () => {
    setShowRecognizeDialog(false);
    clearRecognizedEntities();
    setSelectedRecognizedItems([]);
    setSelectedRecognizedCharacters([]);
    setSelectedRecognizedLandmarks([]);
  };

  // 提交识别的实体
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

  // 切换物品选择
  const toggleItemSelection = (item: RecognizedEntity) => {
    setSelectedRecognizedItems((prev) =>
      prev.some((i) => i.name === item.name)
        ? prev.filter((i) => i.name !== item.name)
        : [...prev, item]
    );
  };

  // 切换人物选择
  const toggleCharacterSelection = (character: RecognizedEntity) => {
    setSelectedRecognizedCharacters((prev) =>
      prev.some((c) => c.name === character.name)
        ? prev.filter((c) => c.name !== character.name)
        : [...prev, character]
    );
  };

  // 切换地点选择
  const toggleLandmarkSelection = (landmark: RecognizedEntity) => {
    setSelectedRecognizedLandmarks((prev) =>
      prev.some((l) => l.name === landmark.name)
        ? prev.filter((l) => l.name !== landmark.name)
        : [...prev, landmark]
    );
  };

  // ==================== 手动添加相关处理函数 ====================

  // 打开手动添加对话框
  const handleOpenAddItem = () => {
    setShowAddItemDialog(true);
    setNewItemName("");
    setGenerateDescForNewItem(true);
  };

  // 关闭手动添加对话框
  const handleCloseAddItem = () => {
    setShowAddItemDialog(false);
    setNewItemName("");
  };

  // 提交手动添加
  const handleSubmitAddItem = async () => {
    if (!newItemName.trim()) return;
    await createItem(gameId, newItemName.trim(), generateDescForNewItem);
    setShowAddItemDialog(false);
    setNewItemName("");
  };

  // ==================== 删除相关处理函数 ====================

  // 打开删除确认
  const handleOpenDeleteConfirm = (type: "character" | "item" | "landmark", name: string) => {
    setEntityToDelete({ type, name });
    setShowDeleteConfirm(true);
  };

  // 关闭删除确认
  const handleCloseDeleteConfirm = () => {
    setShowDeleteConfirm(false);
    setEntityToDelete(null);
  };

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!entityToDelete) return;

    switch (entityToDelete.type) {
      case "character":
        await deleteCharacter(gameId, entityToDelete.name);
        break;
      case "item":
        await deleteItem(gameId, entityToDelete.name);
        break;
      case "landmark":
        await deleteLandmark(gameId, entityToDelete.name);
        break;
    }

    setShowDeleteConfirm(false);
    setEntityToDelete(null);
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 标题 */}
      <div className="p-4 border-b flex-shrink-0">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Package className="w-5 h-5" />
          收集
        </h2>
        <p className="text-sm text-muted-foreground">
          人物、物品和标志物收集记录
        </p>
      </div>

      {/* Tab 按钮 */}
      <div className="px-4 pt-2 flex gap-2 flex-shrink-0">
        <Button
          variant={activeTab === "characters" ? "default" : "outline"}
          size="sm"
          onClick={() => setActiveTab("characters")}
          className="flex-1"
        >
          <User className="w-4 h-4 mr-1" />
          人物 ({characters.length})
        </Button>
        <Button
          variant={activeTab === "items" ? "default" : "outline"}
          size="sm"
          onClick={() => setActiveTab("items")}
          className="flex-1"
        >
          <Package className="w-4 h-4 mr-1" />
          物品 ({items.length})
        </Button>
        <Button
          variant={activeTab === "landmarks" ? "default" : "outline"}
          size="sm"
          onClick={() => setActiveTab("landmarks")}
          className="flex-1"
        >
          <MapPin className="w-4 h-4 mr-1" />
          标志物 ({landmarks.length})
        </Button>
      </div>

      {/* 操作按钮 */}
      <div className="px-4 pt-2 flex gap-2 flex-shrink-0">
        <Button
          variant="outline"
          size="sm"
          onClick={handleOpenRecognize}
          disabled={isRecognizing}
          className="flex-1"
        >
          {isRecognizing ? (
            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
          ) : (
            <Wand2 className="w-4 h-4 mr-1" />
          )}
          智能识别
        </Button>
        {activeTab === "items" && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleOpenAddItem}
            className="flex-1"
          >
            <Plus className="w-4 h-4 mr-1" />
            手动添加
          </Button>
        )}
      </div>

      {/* 可滚动的内容区域 */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4">
          {/* 人物列表 */}
          {activeTab === "characters" && (
            <>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : characters.length === 0 ? (
                <p className="text-muted-foreground text-sm text-center py-8">
                  暂无人物记录
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {characters.map((character) => (
                    <button
                      key={character.name}
                      onClick={() => handleCharacterClick(character)}
                      className="text-left p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
                    >
                      {/* 图片区域 - 使用 object-top 确保显示头部 */}
                      <div className="aspect-[3/4] rounded-md bg-muted mb-2 overflow-hidden flex items-center justify-center">
                        {character.image_url ? (
                          <img
                            src={character.image_url}
                            alt={character.name}
                            className="w-full h-full object-cover object-top"
                          />
                        ) : (
                          <div className="flex flex-col items-center gap-1 text-muted-foreground">
                            <User className="w-8 h-8" />
                            <span className="text-xs">无图片</span>
                          </div>
                        )}
                      </div>

                      {/* 信息 */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-sm truncate">
                            {character.name}
                          </span>
                          {character.image_generated ? (
                            <Badge variant="outline" className="text-xs">
                              <ImageIcon className="w-3 h-3 mr-1" />
                              有图
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs">
                              待生成
                            </Badge>
                          )}
                        </div>
                        {character.role && (
                          <p className="text-xs text-muted-foreground truncate">
                            {character.role}
                          </p>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {/* 物品列表 */}
          {activeTab === "items" && (
            <>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : items.length === 0 ? (
                <p className="text-muted-foreground text-sm text-center py-8">
                  暂无物品记录
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {items.map((item) => (
                    <button
                      key={item.name}
                      onClick={() => handleItemClick(item)}
                      className="text-left p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
                    >
                      {/* 图片区域 */}
                      <div className="aspect-square rounded-md bg-muted mb-2 overflow-hidden flex items-center justify-center">
                        {item.image_url ? (
                          <img
                            src={item.image_url}
                            alt={item.name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="flex flex-col items-center gap-1 text-muted-foreground">
                            <Package className="w-8 h-8" />
                            <span className="text-xs">无图片</span>
                          </div>
                        )}
                      </div>

                      {/* 信息 */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-sm truncate">
                            {item.name}
                          </span>
                          {item.is_key_item && (
                            <Sparkles className="w-3 h-3 text-amber-500" />
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <Badge
                            variant="outline"
                            className="text-xs px-1.5 py-0"
                          >
                            {CATEGORY_LABELS[item.category] || item.category}
                          </Badge>
                          {!item.image_generated && (
                            <Badge variant="secondary" className="text-xs px-1.5 py-0">
                              待生成
                            </Badge>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {/* 标志物列表 */}
          {activeTab === "landmarks" && (
            <>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : landmarks.length === 0 ? (
                <p className="text-muted-foreground text-sm text-center py-8">
                  暂无标志物记录
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {landmarks.map((landmark) => (
                    <button
                      key={landmark.name}
                      onClick={() => handleLandmarkClick(landmark)}
                      className="text-left p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
                    >
                      {/* 图片区域 */}
                      <div className="aspect-video rounded-md bg-muted mb-2 overflow-hidden flex items-center justify-center">
                        {landmark.image_url ? (
                          <img
                            src={landmark.image_url}
                            alt={landmark.name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="flex flex-col items-center gap-1 text-muted-foreground">
                            <MapPin className="w-8 h-8" />
                            <span className="text-xs">无图片</span>
                          </div>
                        )}
                      </div>

                      {/* 信息 */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-sm truncate">
                            {landmark.name}
                          </span>
                          {landmark.is_key_location && (
                            <Sparkles className="w-3 h-3 text-amber-500" />
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <Badge
                            variant="outline"
                            className="text-xs px-1.5 py-0"
                          >
                            {LANDMARK_CATEGORY_LABELS[landmark.category] || landmark.category}
                          </Badge>
                          {!landmark.image_generated && (
                            <Badge variant="secondary" className="text-xs px-1.5 py-0">
                              待生成
                            </Badge>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </ScrollArea>

      {/* 人物详情弹窗 - 添加滚动支持 */}
      <Dialog open={!!selectedCharacter} onOpenChange={() => handleCloseDetail()}>
        <DialogContent className="max-w-md h-[85vh] flex flex-col p-0 gap-0">
          {selectedCharacter && (
            <>
              <DialogHeader className="px-6 pt-6 pb-2 flex-shrink-0">
                <div className="flex items-start justify-between">
                  <div>
                    <DialogTitle className="flex items-center gap-2">
                      <User className="w-5 h-5" />
                      {selectedCharacter.name}
                    </DialogTitle>
                    <DialogDescription>
                      {selectedCharacter.role || "故事中的人物"}
                    </DialogDescription>
                  </div>
                  {/* 删除按钮 */}
                  {selectedCharacter.role !== "主角" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                      onClick={() => handleOpenDeleteConfirm("character", selectedCharacter.name)}
                      disabled={isDeleting}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </DialogHeader>

              <div className="flex-1 overflow-y-auto px-6 pb-6">
                <div className="space-y-4">
                  {/* 图片 - 使用 object-top 确保显示头部 */}
                  <div className="aspect-[3/4] rounded-lg bg-muted overflow-hidden">
                    {selectedCharacter.image_url ? (
                      <img
                        src={selectedCharacter.image_url}
                        alt={selectedCharacter.name}
                        className="w-full h-full object-cover object-top"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <div className="text-center text-muted-foreground">
                          <User className="w-16 h-16 mx-auto mb-2" />
                          <p className="text-sm">暂无图片</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 生成按钮 */}
                  {!selectedCharacter.image_generated ? (
                    <Button
                      className="w-full"
                      onClick={() => handleGenerateCharacterImage(selectedCharacter.name)}
                      disabled={generatingImageFor === selectedCharacter.name}
                    >
                      {generatingImageFor === selectedCharacter.name ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          生成中...
                        </>
                      ) : (
                        <>
                          <ImageIcon className="w-4 h-4 mr-2" />
                          生成图片
                        </>
                      )}
                    </Button>
                  ) : (
                    <div className="space-y-2">
                      {/* 已有图片时显示修改按钮 */}
                      {!showRegenerateInput || regenerateType !== "character" ? (
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={handleStartRegenerateCharacter}
                          disabled={regeneratingImageFor === selectedCharacter.name}
                        >
                          {regeneratingImageFor === selectedCharacter.name ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              修改中...
                            </>
                          ) : (
                            <>
                              <Pencil className="w-4 h-4 mr-2" />
                              修改画像
                            </>
                          )}
                        </Button>
                      ) : (
                        // 修改输入框
                        <div className="space-y-2">
                          <Textarea
                            placeholder="输入修改意见，例如：头发变长一点、换一件蓝色衣服..."
                            value={regenerateFeedback}
                            onChange={(e) => setRegenerateFeedback(e.target.value)}
                            className="min-h-[80px] resize-none"
                            disabled={regeneratingImageFor === selectedCharacter.name}
                          />
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              className="flex-1"
                              onClick={handleCancelRegenerate}
                              disabled={regeneratingImageFor === selectedCharacter.name}
                            >
                              <X className="w-4 h-4 mr-1" />
                              取消
                            </Button>
                            <Button
                              className="flex-1"
                              onClick={handleSubmitRegenerateCharacter}
                              disabled={!regenerateFeedback.trim() || regeneratingImageFor === selectedCharacter.name}
                            >
                              {regeneratingImageFor === selectedCharacter.name ? (
                                <>
                                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                  修改中...
                                </>
                              ) : (
                                <>
                                  <Pencil className="w-4 h-4 mr-2" />
                                  提交修改
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 亲密度提示 */}
                  {selectedCharacter.image_generated && selectedCharacter.affinity <= 50 && selectedCharacter.role !== "主角" && (
                    <p className="text-xs text-muted-foreground text-center">
                      亲密度需大于50才能修改画像
                    </p>
                  )}

                  {/* 详细信息 */}
                  <div className="space-y-3 text-sm">
                    {selectedCharacter.description && (
                      <div>
                        <span className="font-medium">描述：</span>
                        <p className="text-muted-foreground mt-1">
                          {selectedCharacter.description}
                        </p>
                      </div>
                    )}
                    {selectedCharacter.age && (
                      <div>
                        <span className="font-medium">年龄：</span>
                        <span className="text-muted-foreground">
                          {selectedCharacter.age} 岁
                        </span>
                      </div>
                    )}
                    {selectedCharacter.occupation && (
                      <div>
                        <span className="font-medium">职业：</span>
                        <span className="text-muted-foreground">
                          {selectedCharacter.occupation}
                        </span>
                      </div>
                    )}
                    <div>
                      <span className="font-medium">亲密度：</span>
                      <span className="text-muted-foreground">
                        {selectedCharacter.affinity}/100
                      </span>
                    </div>
                    {selectedCharacter.personality_traits.length > 0 && (
                      <div>
                        <span className="font-medium">性格：</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {selectedCharacter.personality_traits.map((trait, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">
                              {trait}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* 物品详情弹窗 - 添加滚动支持 */}
      <Dialog open={!!selectedItem} onOpenChange={() => handleCloseDetail()}>
        <DialogContent className="max-w-md h-[85vh] flex flex-col p-0 gap-0">
          {selectedItem && (
            <>
              <DialogHeader className="px-6 pt-6 pb-2 flex-shrink-0">
                <div className="flex items-start justify-between">
                  <div>
                    <DialogTitle className="flex items-center gap-2">
                      <Package className="w-5 h-5" />
                      {selectedItem.name}
                      {selectedItem.is_key_item && (
                        <Sparkles className="w-4 h-4 text-amber-500" />
                      )}
                    </DialogTitle>
                    <DialogDescription>
                      {CATEGORY_LABELS[selectedItem.category] || selectedItem.category}
                      · {IMPORTANCE_LABELS[selectedItem.importance]?.label || "普通"}
                    </DialogDescription>
                  </div>
                  {/* 删除按钮 */}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => handleOpenDeleteConfirm("item", selectedItem.name)}
                    disabled={isDeleting}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </DialogHeader>

              <div className="flex-1 overflow-y-auto px-6 pb-6">
                <div className="space-y-4">
                  {/* 图片 */}
                  <div className="aspect-square rounded-lg bg-muted overflow-hidden">
                    {selectedItem.image_url ? (
                      <img
                        src={selectedItem.image_url}
                        alt={selectedItem.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <div className="text-center text-muted-foreground">
                          <Package className="w-16 h-16 mx-auto mb-2" />
                          <p className="text-sm">暂无图片</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 生成按钮 */}
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      {!selectedItem.image_generated ? (
                        <Button
                          className="flex-1"
                          onClick={() => handleGenerateItemImage(selectedItem.name)}
                          disabled={generatingImageFor === selectedItem.name}
                        >
                          {generatingImageFor === selectedItem.name ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              生成中...
                            </>
                          ) : (
                            <>
                              <ImageIcon className="w-4 h-4 mr-2" />
                              生成图片
                            </>
                          )}
                        </Button>
                      ) : (
                        // 已有图片时显示修改按钮
                        <Button
                          variant="outline"
                          className="flex-1"
                          onClick={handleStartRegenerateItem}
                          disabled={regeneratingImageFor === selectedItem.name}
                        >
                          {regeneratingImageFor === selectedItem.name ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              修改中...
                            </>
                          ) : (
                            <>
                              <Pencil className="w-4 h-4 mr-2" />
                              修改图片
                            </>
                          )}
                        </Button>
                      )}
                      {!selectedItem.description_generated && !selectedItem.description && (
                        <Button
                          variant="outline"
                          className="flex-1"
                          onClick={() => handleGenerateItemDescription(selectedItem.name)}
                          disabled={generatingDescriptionFor === selectedItem.name}
                        >
                          {generatingDescriptionFor === selectedItem.name ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              生成中...
                            </>
                          ) : (
                            <>
                              <FileText className="w-4 h-4 mr-2" />
                              生成描述
                            </>
                          )}
                        </Button>
                      )}
                    </div>

                    {/* 修改图片输入框 */}
                    {showRegenerateInput && regenerateType === "item" && selectedItem.image_generated && (
                      <div className="space-y-2">
                        <Textarea
                          placeholder="输入修改意见，例如：颜色改深一点、增加细节..."
                          value={regenerateFeedback}
                          onChange={(e) => setRegenerateFeedback(e.target.value)}
                          className="min-h-[80px] resize-none"
                          disabled={regeneratingImageFor === selectedItem.name}
                        />
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            className="flex-1"
                            onClick={handleCancelRegenerate}
                            disabled={regeneratingImageFor === selectedItem.name}
                          >
                            <X className="w-4 h-4 mr-1" />
                            取消
                          </Button>
                          <Button
                            className="flex-1"
                            onClick={handleSubmitRegenerateItem}
                            disabled={!regenerateFeedback.trim() || regeneratingImageFor === selectedItem.name}
                          >
                            {regeneratingImageFor === selectedItem.name ? (
                              <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                修改中...
                              </>
                            ) : (
                              <>
                                <Pencil className="w-4 h-4 mr-2" />
                                提交修改
                              </>
                            )}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 详细信息 */}
                  <div className="space-y-3 text-sm">
                    {selectedItem.description && (
                      <div>
                        <span className="font-medium">描述：</span>
                        <p className="text-muted-foreground mt-1">
                          {selectedItem.description}
                        </p>
                      </div>
                    )}
                    {selectedItem.acquired_context && (
                      <div>
                        <span className="font-medium">获得场景：</span>
                        <p className="text-muted-foreground mt-1">
                          {selectedItem.acquired_context}
                        </p>
                      </div>
                    )}
                    <div>
                      <span className="font-medium">获得时间：</span>
                      <span className="text-muted-foreground">
                        第 {selectedItem.acquired_week + 1} 周
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* 标志物详情弹窗 */}
      <Dialog open={!!selectedLandmark} onOpenChange={() => handleCloseDetail()}>
        <DialogContent className="max-w-md h-[85vh] flex flex-col p-0 gap-0">
          {selectedLandmark && (
            <>
              <DialogHeader className="px-6 pt-6 pb-2 flex-shrink-0">
                <div className="flex items-start justify-between">
                  <div>
                    <DialogTitle className="flex items-center gap-2">
                      <MapPin className="w-5 h-5" />
                      {selectedLandmark.name}
                      {selectedLandmark.is_key_location && (
                        <Sparkles className="w-4 h-4 text-amber-500" />
                      )}
                    </DialogTitle>
                    <DialogDescription>
                      {LANDMARK_CATEGORY_LABELS[selectedLandmark.category] || selectedLandmark.category}
                      · {IMPORTANCE_LABELS[selectedLandmark.importance]?.label || "普通"}
                    </DialogDescription>
                  </div>
                  {/* 删除按钮 */}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => handleOpenDeleteConfirm("landmark", selectedLandmark.name)}
                    disabled={isDeleting}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </DialogHeader>

              <div className="flex-1 overflow-y-auto px-6 pb-6">
                <div className="space-y-4">
                  {/* 图片 */}
                  <div className="aspect-video rounded-lg bg-muted overflow-hidden">
                    {selectedLandmark.image_url ? (
                      <img
                        src={selectedLandmark.image_url}
                        alt={selectedLandmark.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <div className="text-center text-muted-foreground">
                          <MapPin className="w-16 h-16 mx-auto mb-2" />
                          <p className="text-sm">暂无图片</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 生成按钮 */}
                  <div className="flex gap-2">
                    {!selectedLandmark.image_generated ? (
                      <Button
                        className="flex-1"
                        onClick={() => handleGenerateLandmarkImage(selectedLandmark.name)}
                        disabled={generatingImageFor === selectedLandmark.name}
                      >
                        {generatingImageFor === selectedLandmark.name ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            生成中...
                          </>
                        ) : (
                          <>
                            <ImageIcon className="w-4 h-4 mr-2" />
                            生成图片
                          </>
                        )}
                      </Button>
                    ) : null}
                    {!selectedLandmark.description && (
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={() => handleGenerateLandmarkDescription(selectedLandmark.name)}
                        disabled={generatingDescriptionFor === selectedLandmark.name}
                      >
                        {generatingDescriptionFor === selectedLandmark.name ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            生成中...
                          </>
                        ) : (
                          <>
                            <FileText className="w-4 h-4 mr-2" />
                            生成描述
                          </>
                        )}
                      </Button>
                    )}
                  </div>

                  {/* 详细信息 */}
                  <div className="space-y-3 text-sm">
                    {selectedLandmark.description && (
                      <div>
                        <span className="font-medium">描述：</span>
                        <p className="text-muted-foreground mt-1">
                          {selectedLandmark.description}
                        </p>
                      </div>
                    )}
                    {selectedLandmark.context && (
                      <div>
                        <span className="font-medium">场景：</span>
                        <p className="text-muted-foreground mt-1">
                          {selectedLandmark.context}
                        </p>
                      </div>
                    )}
                    <div className="flex gap-4">
                      <div>
                        <span className="font-medium">首次出现：</span>
                        <span className="text-muted-foreground">
                          第 {selectedLandmark.first_appear_week + 1} 周
                        </span>
                      </div>
                      <div>
                        <span className="font-medium">出现次数：</span>
                        <span className="text-muted-foreground">
                          {selectedLandmark.appear_count} 次
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* 错误提示 */}
      {error && (
        <div className="p-4 border-t bg-destructive/10 flex-shrink-0">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="ghost" size="sm" onClick={clearError}>
            关闭
          </Button>
        </div>
      )}

      {/* 智能识别对话框 */}
      <Dialog open={showRecognizeDialog} onOpenChange={handleCloseRecognize}>
        <DialogContent className="max-w-lg max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wand2 className="w-5 h-5" />
              智能识别
            </DialogTitle>
            <DialogDescription>
              从历史故事中识别重复出现的物品、人物、地点
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto py-4">
            {isRecognizing ? (
              <div className="flex flex-col items-center justify-center py-8 gap-3">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">正在分析故事历史...</p>
              </div>
            ) : recognizedEntities ? (
              <div className="space-y-4">
                {/* 物品 */}
                {recognizedEntities.items && recognizedEntities.items.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2 flex items-center gap-2">
                      <Package className="w-4 h-4" />
                      识别到的物品 ({recognizedEntities.items.length})
                    </h4>
                    <div className="space-y-2">
                      {recognizedEntities.items.map((item: RecognizedEntity) => (
                        <label
                          key={item.name}
                          className="flex items-start gap-2 p-2 rounded border hover:bg-accent cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            className="mt-1"
                            checked={selectedRecognizedItems.some((i) => i.name === item.name)}
                            onChange={() => toggleItemSelection(item)}
                          />
                          <div className="flex-1 text-sm">
                            <div className="font-medium">{item.name}</div>
                            <div className="text-muted-foreground text-xs">
                              出现 {item.appear_count} 次 · {item.description.slice(0, 50)}...
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* 人物 */}
                {recognizedEntities.characters && recognizedEntities.characters.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2 flex items-center gap-2">
                      <User className="w-4 h-4" />
                      识别到的人物 ({recognizedEntities.characters.length})
                    </h4>
                    <div className="space-y-2">
                      {recognizedEntities.characters.map((char: RecognizedEntity) => (
                        <label
                          key={char.name}
                          className="flex items-start gap-2 p-2 rounded border hover:bg-accent cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            className="mt-1"
                            checked={selectedRecognizedCharacters.some((c) => c.name === char.name)}
                            onChange={() => toggleCharacterSelection(char)}
                          />
                          <div className="flex-1 text-sm">
                            <div className="font-medium">{char.name}</div>
                            <div className="text-muted-foreground text-xs">
                              出现 {char.appear_count} 次 · {char.description.slice(0, 50)}...
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* 地点 */}
                {recognizedEntities.landmarks && recognizedEntities.landmarks.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2 flex items-center gap-2">
                      <MapPin className="w-4 h-4" />
                      识别到的地点 ({recognizedEntities.landmarks.length})
                    </h4>
                    <div className="space-y-2">
                      {recognizedEntities.landmarks.map((landmark: RecognizedEntity) => (
                        <label
                          key={landmark.name}
                          className="flex items-start gap-2 p-2 rounded border hover:bg-accent cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            className="mt-1"
                            checked={selectedRecognizedLandmarks.some((l) => l.name === landmark.name)}
                            onChange={() => toggleLandmarkSelection(landmark)}
                          />
                          <div className="flex-1 text-sm">
                            <div className="font-medium">{landmark.name}</div>
                            <div className="text-muted-foreground text-xs">
                              出现 {landmark.appear_count} 次 · {landmark.description.slice(0, 50)}...
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* 无结果提示 */}
                {recognizedEntities.items?.length === 0 &&
                  recognizedEntities.characters?.length === 0 &&
                  recognizedEntities.landmarks?.length === 0 && (
                    <div className="text-center py-8 text-muted-foreground">
                      <AlertCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p>未识别到新的实体</p>
                      <p className="text-xs mt-1">可能故事还不够长，或已有所有实体</p>
                    </div>
                  )}
              </div>
            ) : null}
          </div>

          <div className="flex gap-2 pt-4 border-t">
            <Button variant="outline" onClick={handleCloseRecognize} className="flex-1">
              取消
            </Button>
            <Button
              onClick={handleSubmitRecognizedEntities}
              disabled={
                isLoading ||
                (selectedRecognizedItems.length === 0 &&
                  selectedRecognizedCharacters.length === 0 &&
                  selectedRecognizedLandmarks.length === 0)
              }
              className="flex-1"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  添加中...
                </>
              ) : (
                <>
                  添加到收集
                  {selectedRecognizedItems.length + selectedRecognizedCharacters.length + selectedRecognizedLandmarks.length > 0 && (
                    <span className="ml-1">
                      ({selectedRecognizedItems.length + selectedRecognizedCharacters.length + selectedRecognizedLandmarks.length})
                    </span>
                  )}
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* 手动添加物品对话框 */}
      <Dialog open={showAddItemDialog} onOpenChange={handleCloseAddItem}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="w-5 h-5" />
              手动添加物品
            </DialogTitle>
            <DialogDescription>
              输入物品名称，AI将从故事历史中提取描述
            </DialogDescription>
          </DialogHeader>

          <div className="py-4 space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">物品名称</label>
              <input
                type="text"
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                placeholder="例如：神秘古书、银色怀表..."
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newItemName.trim()) {
                    handleSubmitAddItem();
                  }
                }}
              />
            </div>

            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={generateDescForNewItem}
                onChange={(e) => setGenerateDescForNewItem(e.target.checked)}
              />
              从故事历史中提取描述
            </label>
          </div>

          <div className="flex gap-2 pt-4 border-t">
            <Button variant="outline" onClick={handleCloseAddItem} className="flex-1">
              取消
            </Button>
            <Button
              onClick={handleSubmitAddItem}
              disabled={!newItemName.trim() || isLoading}
              className="flex-1"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  创建中...
                </>
              ) : (
                "创建"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={showDeleteConfirm} onOpenChange={handleCloseDeleteConfirm}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="w-5 h-5" />
              确认删除
            </DialogTitle>
            <DialogDescription>
              {entityToDelete && (
                <>
                  确定要删除
                  <span className="font-medium mx-1">{entityToDelete.name}</span>
                  吗？此操作不可恢复。
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="flex gap-2 pt-4">
            <Button variant="outline" onClick={handleCloseDeleteConfirm} className="flex-1">
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={isDeleting}
              className="flex-1"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                "删除"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}