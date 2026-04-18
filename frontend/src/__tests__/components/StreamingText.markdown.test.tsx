/**
 * StreamingText Markdown 渲染测试
 */
import { render, screen } from "@testing-library/react";
import { StreamingText } from "@/components/game/StreamingText";

// Mock react-markdown
jest.mock("react-markdown", () => {
  return jest.fn(({ children }) => (
    <div data-testid="react-markdown">{children}</div>
  ));
});

jest.mock("remark-gfm", () => "remark-gfm");

// JSDOM does not support scrollTo
Object.defineProperty(Element.prototype, "scrollTo", {
  writable: true,
  value: jest.fn(),
});

describe("StreamingText markdown rendering", () => {
  it("uses ReactMarkdown for narrative text", () => {
    render(<StreamingText text="**Bold text**" isStreaming={false} narrative />);
    expect(screen.getByTestId("react-markdown")).toBeInTheDocument();
  });

  it("preserves streaming cursor while using ReactMarkdown", () => {
    const { container } = render(
      <StreamingText text="Hello" isStreaming={true} narrative />
    );
    expect(container.querySelector(".typewriter-cursor")).toBeInTheDocument();
  });

  it("does not use ReactMarkdown when narrative is false", () => {
    render(<StreamingText text="Plain text" isStreaming={false} narrative={false} />);
    expect(screen.queryByTestId("react-markdown")).not.toBeInTheDocument();
    expect(screen.getByText("Plain text")).toBeInTheDocument();
  });
});
