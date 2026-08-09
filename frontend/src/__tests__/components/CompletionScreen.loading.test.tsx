import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CompletionScreen } from "@/components/create/CompletionScreen";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

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
  presetSaveStatus: "idle" as const,
  presetSaveMessage: "",
  toast: null,
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

  test("uses one page transition and one reading surface", () => {
    const { container } = render(<CompletionScreen {...defaultProps} />);

    expect(container.querySelectorAll('main[data-slot="page-transition"]')).toHaveLength(1);
    expect(container.querySelectorAll('main main')).toHaveLength(0);
    expect(container.querySelectorAll('[data-slot="surface"][data-variant="reading"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(0);
  });

  test("uses the full reading width when no portrait image exists", () => {
    render(<CompletionScreen {...defaultProps} playerImages={[]} />);

    const heading = screen.getByRole("heading", {
      name: "角色设定完成",
      level: 1,
    });
    const overview = heading.closest("section");

    expect(overview).not.toBeNull();
    expect(overview?.children).toHaveLength(1);
    expect(overview?.firstElementChild).toContainElement(heading);
    expect(overview).not.toHaveClass("grid");
    expect(overview).not.toHaveClass("gap-8");
    expect(overview?.className).not.toContain("md:grid-cols-");
  });

  test("restores the portrait track only when an image exists", () => {
    render(<CompletionScreen {...defaultProps} />);

    const heading = screen.getByRole("heading", {
      name: "角色设定完成",
      level: 1,
    });
    const overview = heading.closest("section");

    expect(overview).toHaveClass("grid", "gap-8");
    expect(overview?.className).toContain(
      "md:grid-cols-[10rem_minmax(0,1fr)]",
    );
    expect(overview?.children).toHaveLength(2);
  });

  test("keeps completion actions at the touch target size", () => {
    render(<CompletionScreen {...defaultProps} />);

    for (const name of ["返回修改", "快速保存", "查看设定详情", "开始游戏", "保存为预设"]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute("data-size", "touch");
    }
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

    expect(screen.getByRole("button", { name: "快速保存" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存为预设" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认保存" })).not.toBeInTheDocument();
  });

  test("sheet uses confirm save wording", () => {
    render(<CompletionScreen {...defaultProps} showPresetSheet={true} />);

    expect(document.querySelector('[data-slot="preset-save-sheet"]')).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认保存" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭保存预设" })).toHaveAttribute(
      "data-size",
      "icon-touch",
    );
    const input = screen.getByRole("textbox", { name: "预设名称" });
    expect(input).toHaveAttribute("aria-describedby");
    expect(input.getAttribute("aria-describedby")).toContain("preset-name-count");
  });

  test("sheet blocks an injected overlimit preset name", () => {
    const onSavePreset = jest.fn();
    render(
      <CompletionScreen
        {...defaultProps}
        showPresetSheet={true}
        presetName={"😀".repeat(INPUT_LIMITS.name + 1)}
        onSavePreset={onSavePreset}
      />
    );
    expect(screen.getByText("已超出 1 字")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "预设名称" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByRole("button", { name: "确认保存" })).toBeDisabled();
    expect(onSavePreset).not.toHaveBeenCalled();
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
