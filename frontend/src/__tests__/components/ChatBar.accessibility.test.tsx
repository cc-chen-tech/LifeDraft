/**
 * ChatBar 可访问性测试
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatBar } from "@/components/game/ChatBar";

// Mock scrollTo for JSDOM
Object.defineProperty(Element.prototype, "scrollTo", {
  writable: true,
  value: jest.fn(),
});

describe("ChatBar accessibility", () => {
  it("close button has aria-label when expanded", async () => {
    render(<ChatBar gameId={1} onSave={jest.fn()} />);
    // ChatBar starts collapsed, click chat expand button
    const expandBtn = screen.getByLabelText("打开聊天");
    await userEvent.click(expandBtn);
    await waitFor(() => {
      expect(screen.getByLabelText("关闭聊天")).toBeInTheDocument();
    });
  });

  it("send button has aria-label", async () => {
    render(<ChatBar gameId={1} onSave={jest.fn()} />);
    const expandBtn = screen.getByLabelText("打开聊天");
    await userEvent.click(expandBtn);
    await waitFor(() => {
      expect(screen.getByLabelText("发送消息")).toBeInTheDocument();
    });
  });
});
