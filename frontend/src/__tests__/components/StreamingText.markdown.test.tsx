/**
 * StreamingText Markdown 渲染测试
 */
import { render, screen } from "@testing-library/react";
import { StreamingText } from "@/components/game/StreamingText";

// react-markdown and remark-gfm are globally mocked in jest.setup.js

describe("StreamingText markdown rendering", () => {
  it("uses ReactMarkdown for narrative text", () => {
    render(<StreamingText text="**Bold text**" isStreaming={false} narrative />);
    expect(document.querySelector(".markdown-mock")).toBeInTheDocument();
  });

  it("preserves streaming cursor while using ReactMarkdown", () => {
    const { container } = render(
      <StreamingText text="Hello" isStreaming={true} narrative />
    );
    expect(container.querySelector(".typewriter-cursor")).toBeInTheDocument();
  });

  it("does not use ReactMarkdown when narrative is false", () => {
    render(<StreamingText text="Plain text" isStreaming={false} narrative={false} />);
    expect(document.querySelector(".markdown-mock")).not.toBeInTheDocument();
    expect(screen.getByText("Plain text")).toBeInTheDocument();
  });
});
