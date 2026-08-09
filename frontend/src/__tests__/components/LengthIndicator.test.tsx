import { render, screen } from "@testing-library/react";

import { LengthIndicator } from "@/components/ui/length-indicator";

describe("LengthIndicator", () => {
  it("uses the readable secondary token for remaining-count copy", () => {
    render(<LengthIndicator value="墨页" limit={50} />);

    expect(screen.getByText("还可输入 48 字")).toHaveClass(
      "text-[var(--text-secondary)]",
    );
  });

  it("uses the danger foreground for an over-limit alert", () => {
    render(<LengthIndicator value="墨页草稿" limit={3} />);

    expect(screen.getByRole("alert")).toHaveClass("text-destructive");
  });

  it("can render a static described-by counter without creating another live region", () => {
    render(
      <LengthIndicator
        id="character-name-count"
        value="墨页"
        limit={50}
        announce={false}
      />,
    );

    const counter = screen.getByText("还可输入 48 字");
    expect(counter).toHaveAttribute("id", "character-name-count");
    expect(counter).not.toHaveAttribute("aria-live");
    expect(counter).not.toHaveAttribute("role");
  });
});
