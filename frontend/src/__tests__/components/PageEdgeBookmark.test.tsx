import * as Story101 from "@/components/story101";
import { render, screen } from "@testing-library/react";

describe("PageEdgeBookmark", () => {
  it("is exported by the shared story101 component boundary", () => {
    expect(Story101).toHaveProperty("PageEdgeBookmark");
  });

  it("names one informational landmark without pretending to be navigation", () => {
    render(
      <Story101.PageEdgeBookmark
        label="时代背景"
        detail="第 1 步，共 5 步"
      />,
    );

    const bookmark = screen.getByRole("complementary", {
      name: "当前页面位置",
    });
    expect(bookmark).toHaveTextContent("时代背景");
    expect(bookmark).toHaveTextContent("第 1 步，共 5 步");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
