/**
 * StreamingText "flash" effect test
 *
 * When isStreaming flips from true -> false, the component should NOT
 * instantly reveal all remaining text. The typewriter should keep
 * running until it catches up with the full text.
 */

import React from "react";
import { render, act } from "@testing-library/react";
import { StreamingText } from "@/components/game/StreamingText";

// JSDOM does not implement scrollTo
HTMLElement.prototype.scrollTo = jest.fn();

jest.useFakeTimers();

describe("StreamingText — no flash on isStreaming=false", () => {
  afterEach(() => {
    jest.clearAllTimers();
  });

  it("does not instantly show all text when isStreaming becomes false", () => {
    const { rerender } = render(
      <StreamingText
        text="Hello world!"
        isStreaming={true}
        charsPerFrame={2}
        frameInterval={30}
      />
    );

    // After first interval tick: "He" (2 chars)
    act(() => {
      jest.advanceTimersByTime(30);
    });

    // Now flip isStreaming to false — old code would instantly show "Hello world!"
    rerender(
      <StreamingText
        text="Hello world!"
        isStreaming={false}
        charsPerFrame={2}
        frameInterval={30}
      />
    );

    // Immediately after rerender, should still show only what was typed so far
    // (not the full 12 chars instantly)
    const container = document.querySelector(".overflow-y-auto");
    expect(container!.textContent).not.toBe("Hello world!");
  });

  it("continues typing remaining text after isStreaming becomes false", () => {
    const { rerender } = render(
      <StreamingText
        text="Hello world!"
        isStreaming={true}
        charsPerFrame={2}
        frameInterval={30}
      />
    );

    // Type 2 chars
    act(() => {
      jest.advanceTimersByTime(30);
    });

    // Stop streaming
    rerender(
      <StreamingText
        text="Hello world!"
        isStreaming={false}
        charsPerFrame={2}
        frameInterval={30}
      />
    );

    // Continue advancing — should keep typing
    act(() => {
      jest.advanceTimersByTime(30 * 10); // enough ticks to finish
    });

    const container = document.querySelector(".overflow-y-auto");
    expect(container!.textContent).toBe("Hello world!");
  });

  it("resets displayed text when text prop is cleared", () => {
    const { rerender } = render(
      <StreamingText
        text="First story"
        isStreaming={true}
        charsPerFrame={10}
        frameInterval={30}
      />
    );

    // Finish typing
    act(() => {
      jest.advanceTimersByTime(30);
    });

    // Clear text (e.g. new round) — also stop streaming
    rerender(
      <StreamingText
        text=""
        isStreaming={false}
        charsPerFrame={10}
        frameInterval={30}
      />
    );

    const container = document.querySelector(".overflow-y-auto");
    expect(container).toBeNull(); // !displayedText && !isStreaming → return null
  });
});
