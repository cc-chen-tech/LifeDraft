import { render, screen } from "@testing-library/react";

import { PresetSaveInlineStatus } from "@/components/create/PresetSaveInlineStatus";

describe("PresetSaveInlineStatus", () => {
  it("renders no live region while idle", () => {
    const { container } = render(
      <PresetSaveInlineStatus status="idle" message="" />,
    );

    expect(container.querySelector("[aria-live]")).not.toBeInTheDocument();
  });

  it("uses the shared notice for the real saving state", () => {
    const { container } = render(
      <PresetSaveInlineStatus status="saving" message="正在保存角色预设..." />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("正在保存角色预设...");
    expect(container.querySelector('[data-slot="feedback-notice"]')).toBeInTheDocument();
  });

  it("uses one danger alert for a retryable save error", () => {
    const { container } = render(
      <PresetSaveInlineStatus
        status="error"
        message="保存失败，预设未保存，请重试。"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "保存失败，预设未保存，请重试。",
    );
    expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1);
    expect(container.querySelector('[data-slot="feedback-notice"]')).toBeInTheDocument();
  });
});
