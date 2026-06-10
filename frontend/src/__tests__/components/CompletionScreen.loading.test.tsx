import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CompletionScreen } from "@/components/create/CompletionScreen";

const defaultProps = {
  playerName: "测试角色",
  playerImages: [{ image_id: 1, image_url: "https://example.com/img.jpg" }],
  selectedImageIndex: 0,
  characterSettings: {
    era: { era_description: "古代" },
    gender: { gender: "男", description: "年轻男子" },
  },
  isPresetLoaded: false,
  isGenerating: false,
  hasBasicInfo: true,
  showDetails: false,
  showPresetSheet: false,
  presetName: "",
  isSavingPreset: false,
  isGeneratingImage: false,
  imageFeedback: "",
  onImageFeedbackChange: jest.fn(),
  onRegenerateImage: jest.fn(),
  onRegenerateFreshImage: jest.fn().mockResolvedValue(undefined),
  showToast: jest.fn(),
  onSetShowDetails: jest.fn(),
  onSetShowPresetSheet: jest.fn(),
  onSetPresetName: jest.fn(),
  onBack: jest.fn().mockResolvedValue(undefined),
  onStartGame: jest.fn().mockResolvedValue(undefined),
  onSavePreset: jest.fn().mockResolvedValue(undefined),
  onRegenerateSetting: jest.fn().mockResolvedValue(undefined),
};

describe("CompletionScreen - Loading Feedback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("返回修改按钮点击后立即禁用", async () => {
    render(<CompletionScreen {...defaultProps} />
    );

    const backButton = screen.getByRole("button", { name: /返回修改/i });
    expect(backButton).not.toBeDisabled();

    fireEvent.click(backButton);

    // 按钮应立即禁用（防止重复点击）
    await waitFor(() => {
      expect(backButton).toBeDisabled();
    }, { timeout: 100 });
  });

  test("header preset button uses disambiguated copy", () => {
    render(<CompletionScreen {...defaultProps} />);

    expect(screen.getAllByRole("button", { name: "保存为预设" })).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "确认保存" })).not.toBeInTheDocument();
  });

  test("sheet uses confirm save wording", () => {
    render(<CompletionScreen {...defaultProps} showPresetSheet={true} />);

    expect(screen.getByRole("button", { name: "确认保存" })).toBeInTheDocument();
  });

  test("完全重生成按钮点击后进入加载状态", async () => {
    // 模拟一个慢速的重新生成
    const slowRegenerate = jest.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 500))
    );

    render(
      <CompletionScreen
        {...defaultProps}
        onRegenerateFreshImage={slowRegenerate}
      />
    );

    const regenerateButton = screen.getByRole("button", { name: /完全重生成/i });
    expect(regenerateButton).not.toBeDisabled();

    fireEvent.click(regenerateButton);

    // 按钮应立即禁用/加载
    await waitFor(() => {
      expect(regenerateButton).toBeDisabled();
    }, { timeout: 100 });

    // 等待异步完成
    await waitFor(() => {
      expect(slowRegenerate).toHaveBeenCalledTimes(1);
    });
  });

  test("根据意见修改按钮点击后进入加载状态", async () => {
    const slowRegenerate = jest.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 500))
    );

    render(
      <CompletionScreen
        {...defaultProps}
        imageFeedback="换个风格"
        onRegenerateImage={slowRegenerate}
      />
    );

    const modifyButton = screen.getByRole("button", { name: /根据意见修改/i });
    expect(modifyButton).not.toBeDisabled();

    fireEvent.click(modifyButton);

    await waitFor(() => {
      expect(modifyButton).toBeDisabled();
    }, { timeout: 100 });
  });
});
