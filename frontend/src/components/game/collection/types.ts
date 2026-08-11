/**
 * CollectionPanel 子组件共享的类型定义和常量
 */

import type { CharacterCollectionItem, ItemCollectionItem, LandmarkCollectionItem, RecognizedEntity } from "@/lib/types";

// 物品类别标签
export const CATEGORY_LABELS: Record<string, string> = {
  weapon: "武器",
  tool: "工具",
  keepsake: "纪念品",
  treasure: "宝物",
  document: "文件",
  other: "其他",
};

// 标志物类别标签
export const LANDMARK_CATEGORY_LABELS: Record<string, string> = {
  building: "建筑",
  nature: "自然景观",
  room: "房间",
  area: "区域",
  other: "其他",
};

// 重要程度标签
export const IMPORTANCE_LABELS: Record<string, { label: string; color: string }> = {
  critical: { label: "关键", color: "bg-red-500" },
  important: { label: "重要", color: "bg-amber-500" },
  normal: { label: "普通", color: "bg-gray-400" },
};

// Tab 类型
export type CollectionTab = "characters" | "items" | "landmarks";

// 修改类型
export type RegenerateType = "character" | "item" | null;

// 删除实体类型
export interface EntityToDelete {
  type: "character" | "item" | "landmark";
  name: string;
}

// 人物列表 Props
export interface CharacterListProps {
  characters: CharacterCollectionItem[];
  isLoading: boolean;
  onCharacterClick: (character: CharacterCollectionItem) => void;
}

// 物品列表 Props
export interface ItemListProps {
  items: ItemCollectionItem[];
  isLoading: boolean;
  onItemClick: (item: ItemCollectionItem) => void;
}

// 地标列表 Props
export interface LandmarkListProps {
  landmarks: LandmarkCollectionItem[];
  isLoading: boolean;
  onLandmarkClick: (landmark: LandmarkCollectionItem) => void;
}

// 人物详情 Props
export interface CharacterDetailProps {
  character: CharacterCollectionItem | null;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
  onGenerateImage: (name: string) => Promise<void>;
  onStartRegenerate: () => void;
  onCancelRegenerate: () => void;
  onSubmitRegenerate: () => Promise<void>;
  onOpenDeleteConfirm: (name: string) => void;
  generatingImageFor: string | null;
  regeneratingImageFor: string | null;
  showRegenerateInput: boolean;
  regenerateType: RegenerateType;
  regenerateFeedback: string;
  onRegenerateFeedbackChange: (value: string) => void;
  isDeleting: boolean;
}

// 物品详情 Props
export interface ItemDetailProps {
  item: ItemCollectionItem | null;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
  onGenerateImage: (name: string) => Promise<void>;
  onGenerateDescription: (name: string) => Promise<void>;
  onStartRegenerate: () => void;
  onCancelRegenerate: () => void;
  onSubmitRegenerate: () => Promise<void>;
  onOpenDeleteConfirm: (name: string) => void;
  generatingImageFor: string | null;
  generatingDescriptionFor: string | null;
  regeneratingImageFor: string | null;
  showRegenerateInput: boolean;
  regenerateType: RegenerateType;
  regenerateFeedback: string;
  onRegenerateFeedbackChange: (value: string) => void;
  isDeleting: boolean;
}

// 地标详情 Props
export interface LandmarkDetailProps {
  landmark: LandmarkCollectionItem | null;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
  onGenerateImage: (name: string) => Promise<void>;
  onGenerateDescription: (name: string) => Promise<void>;
  onOpenDeleteConfirm: (name: string) => void;
  generatingImageFor: string | null;
  generatingDescriptionFor: string | null;
  isDeleting: boolean;
}

// 识别对话框 Props
export interface RecognizeDialogProps {
  open: boolean;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
  onSubmit: () => Promise<void>;
  isRecognizing: boolean;
  isLoading: boolean;
  recognizedEntities: {
    items?: RecognizedEntity[];
    characters?: RecognizedEntity[];
    landmarks?: RecognizedEntity[];
  } | null;
  selectedItems: RecognizedEntity[];
  selectedCharacters: RecognizedEntity[];
  selectedLandmarks: RecognizedEntity[];
  onToggleItemSelection: (item: RecognizedEntity) => void;
  onToggleCharacterSelection: (character: RecognizedEntity) => void;
  onToggleLandmarkSelection: (landmark: RecognizedEntity) => void;
}

// 添加物品对话框 Props
export interface AddItemDialogProps {
  open: boolean;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
  onSubmit: () => Promise<void>;
  itemName: string;
  onItemNameChange: (value: string) => void;
  generateDesc: boolean;
  onGenerateDescChange: (value: boolean) => void;
  isLoading: boolean;
}

// 删除确认对话框 Props
export interface DeleteConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
  onConfirm: () => Promise<void>;
  entityToDelete: EntityToDelete | null;
  isDeleting: boolean;
}

// Tab 切换组件 Props
export interface CollectionTabsProps {
  activeTab: CollectionTab;
  onTabChange: (tab: CollectionTab) => void;
  charactersCount: number;
  itemsCount: number;
  landmarksCount: number;
}

// 操作按钮组件 Props
export interface ActionButtonsProps {
  activeTab: CollectionTab;
  isRecognizing: boolean;
  onOpenRecognize: () => void;
  onOpenAddItem: () => void;
}
