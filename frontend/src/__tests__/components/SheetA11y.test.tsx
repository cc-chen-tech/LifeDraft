import { render, screen, waitFor } from "@testing-library/react";

import {
  Sheet,
  SheetContent,
  SheetTitle,
} from "@/components/ui/sheet";

describe("SheetContent accessibility", () => {
  it("does not warn when opened without an explicit SheetDescription", async () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);

    try {
      render(
        <Sheet open>
          <SheetContent>
            <SheetTitle>收集</SheetTitle>
            <button type="button">确认</button>
          </SheetContent>
        </Sheet>
      );

      expect(screen.getByRole("dialog")).toHaveAccessibleDescription();

      await waitFor(() => {
        const consoleOutput =
          warnSpy.mock.calls.flat().join("\n") +
          errorSpy.mock.calls.flat().join("\n");
        expect(consoleOutput).not.toContain("Missing `Description`");
        expect(consoleOutput).not.toContain("Missing Description");
      });
    } finally {
      warnSpy.mockRestore();
      errorSpy.mockRestore();
    }
  });
});
