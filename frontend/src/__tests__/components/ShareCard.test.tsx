/**
 * ShareCard Component Tests
 * Tests the share/social card with download functionality
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShareCard } from "@/components/game/ShareCard";

// Mock html2canvas dynamic import
jest.mock("html2canvas", () => ({
  __esModule: true,
  default: jest.fn().mockResolvedValue({
    toDataURL: jest.fn().mockReturnValue("data:image/png;base64,test"),
  }),
}));

describe("ShareCard", () => {
  const baseProps = {
    playerName: "TestPlayer",
    endingName: "The Hero's Journey",
    lifeMotto: "Never give up",
    achievementCount: 15,
    playDuration: 120,
    children: <div>Summary content</div>,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic rendering", () => {
    it("renders the ending name", () => {
      render(<ShareCard {...baseProps} />);
      expect(screen.getByText("The Hero's Journey")).toBeInTheDocument();
    });

    it("renders the player name with context", () => {
      render(<ShareCard {...baseProps} />);
      expect(screen.getByText("TestPlayer 的人生旅程")).toBeInTheDocument();
    });

    it("renders the life motto in quotes", () => {
      render(<ShareCard {...baseProps} />);
      // Component uses smart quotes (&ldquo; &rdquo; rendered as “ ”)
      expect(screen.getByText(/“Never give up”/)).toBeInTheDocument();
    });

    it("renders achievement count", () => {
      render(<ShareCard {...baseProps} />);
      expect(screen.getByText("15")).toBeInTheDocument();
      expect(screen.getByText("成就")).toBeInTheDocument();
    });

    it("renders play duration", () => {
      render(<ShareCard {...baseProps} />);
      expect(screen.getByText("120分")).toBeInTheDocument();
      expect(screen.getByText("时长")).toBeInTheDocument();
    });

    it("renders children content", () => {
      render(<ShareCard {...baseProps} />);
      expect(screen.getByText("Summary content")).toBeInTheDocument();
    });
  });

  describe("Download button", () => {
    it("renders the download button", () => {
      render(<ShareCard {...baseProps} />);
      expect(screen.getByText("保存分享卡片")).toBeInTheDocument();
    });

    it("is not disabled initially", () => {
      render(<ShareCard {...baseProps} />);
      const button = screen.getByText("保存分享卡片").closest("button");
      expect(button).not.toBeDisabled();
    });

    it("keeps the exported PNG target, render options, and filename stable", async () => {
      const user = userEvent.setup();
      const clickSpy = jest
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => undefined);
      const mockedHtml2canvas = jest.requireMock("html2canvas").default as jest.Mock;

      try {
        render(<ShareCard {...baseProps} />);
        await user.click(screen.getByRole("button", { name: "保存分享卡片" }));

        await waitFor(() => expect(mockedHtml2canvas).toHaveBeenCalledTimes(1));
        const [captureTarget, options] = mockedHtml2canvas.mock.calls[0] as [
          HTMLElement,
          Record<string, unknown>,
        ];
        expect(captureTarget).toContainElement(screen.getByText("The Hero's Journey"));
        expect(options).toEqual({
          backgroundColor: "#0f172a",
          scale: 2,
          useCORS: true,
          logging: false,
        });

        const canvas = await mockedHtml2canvas.mock.results[0].value;
        expect(canvas.toDataURL).toHaveBeenCalledWith("image/png");
        expect(clickSpy).toHaveBeenCalledTimes(1);
        const link = clickSpy.mock.instances[0] as HTMLAnchorElement;
        expect(link.download).toBe("TestPlayer_人生回顾.png");
        expect(link.href).toBe("data:image/png;base64,test");
      } finally {
        clickSpy.mockRestore();
      }
    });
  });

  describe("Footer branding", () => {
    it("shows branding text", () => {
      render(<ShareCard {...baseProps} />);
      expect(
        screen.getByText("人生草稿本 — 用 AI 书写你的故事")
      ).toBeInTheDocument();
    });
  });

  describe("Edge cases", () => {
    it("renders with zero achievements", () => {
      render(<ShareCard {...baseProps} achievementCount={0} />);
      expect(screen.getByText("0")).toBeInTheDocument();
    });

    it("renders with empty life motto", () => {
      render(<ShareCard {...baseProps} lifeMotto="" />);
      // Empty motto renders smart quotes with nothing in between
      expect(screen.getByText(/“”/)).toBeInTheDocument();
    });

    it("renders with empty ending name", () => {
      render(<ShareCard {...baseProps} endingName="" />);
      expect(screen.getByText("TestPlayer 的人生旅程")).toBeInTheDocument();
    });

    it("renders with special characters in player name", () => {
      render(
        <ShareCard
          {...baseProps}
          playerName="!@#$%^&*()"
          lifeMotto="<script>alert('xss')</script>"
        />
      );
      expect(
        screen.getByText("!@#$%^&*() 的人生旅程")
      ).toBeInTheDocument();
    });
  });
});
