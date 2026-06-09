import { render, screen } from "@testing-library/react";

import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";

describe("DialogContent accessibility", () => {
  it("does not warn when opened without an explicit DialogDescription", () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);

    try {
      render(
        <Dialog open>
          <DialogContent>
            <DialogTitle>Test dialog</DialogTitle>
            <button type="button">Confirm</button>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByRole("dialog")).toHaveAccessibleDescription();
      expect(
        warnSpy.mock.calls.flat().join("\n") + errorSpy.mock.calls.flat().join("\n")
      ).not.toContain("Missing Description");
    } finally {
      warnSpy.mockRestore();
      errorSpy.mockRestore();
    }
  });
});
