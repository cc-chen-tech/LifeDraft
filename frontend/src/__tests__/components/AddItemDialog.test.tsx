import { render, screen } from "@testing-library/react";
import { AddItemDialog } from "@/components/game/collection/AddItemDialog";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

describe("AddItemDialog input limit", () => {
  it("keeps an injected overlimit item name visible and blocks creation", () => {
    const onSubmit = jest.fn();
    const value = "😀".repeat(INPUT_LIMITS.name + 1);
    render(
      <AddItemDialog
        open
        onClose={jest.fn()}
        onSubmit={onSubmit}
        itemName={value}
        onItemNameChange={jest.fn()}
        generateDesc={false}
        onGenerateDescChange={jest.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByPlaceholderText(/神秘古书/)).toHaveValue(value);
    expect(screen.getByRole("alert")).toHaveTextContent("已超出 1 字");
    expect(screen.getByRole("button", { name: "创建" })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
