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
  it("expands chat panel when launcher is clicked", async () => {
    render(<ChatBar gameId={1} onSave={jest.fn()} />);
    // ChatBar starts collapsed with launcher button
    const expandBtn = screen.getByLabelText("打开聊天");
    await userEvent.click(expandBtn);
    await waitFor(() => {
      expect(screen.getByTestId("chat-bar-panel")).toBeInTheDocument();
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

  it("does not leave focusable chat controls in the DOM while a story is busy", () => {
    render(<ChatBar gameId={1} onSave={jest.fn()} isStoryBusy />);

    expect(screen.queryByRole("button", { name: "打开聊天" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-bar-launcher")).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-bar-panel")).not.toBeInTheDocument();
  });
});
