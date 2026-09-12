import { render, screen } from "@testing-library/react";
import { AddEntityDialog } from "@/components/game/collection/AddEntityDialog";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

describe("AddEntityDialog input limit", () => {
  it("keeps an injected overlimit item name visible and blocks creation", () => {
    const onSubmit = jest.fn();
    const value = "😀".repeat(INPUT_LIMITS.name + 1);
    render(
      <AddEntityDialog
        activeTab="items"
        open
        onClose={jest.fn()}
        onSubmit={onSubmit}
        entityName={value}
        onEntityNameChange={jest.fn()}
        generateDescription={false}
        onGenerateDescriptionChange={jest.fn()}
        error={null}
        isLoading={false}
      />
    );

    expect(screen.getByPlaceholderText(/神秘古书/)).toHaveValue(value);
    expect(screen.getByRole("alert")).toHaveTextContent("已超出 1 字");
    expect(screen.getByRole("button", { name: "添加" })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
