/**
 * Login Page Accessibility Tests
 * Prevents: snapshot selectors failing, screen-reader incompatibility.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WelcomePage from "@/app/page";

// Mock dependencies
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock("@/stores/useUserStore", () => ({
  useUserStore: () => ({
    isAuthenticated: false,
    user: null,
    register: jest.fn(),
    login: jest.fn(),
    logout: jest.fn(),
    fetchMe: jest.fn(),
  }),
}));

jest.mock("@/stores/useGameStore", () => ({
  useGameStore: () => ({
    gameId: null,
    fetchSavedGames: jest.fn(),
    fetchPresets: jest.fn(),
    resetCreation: jest.fn(),
  }),
}));

jest.mock("@/hooks/useHydration", () => ({
  useHydration: () => true,
}));

// Mock Sheet to render inline in tests (Radix UI portals don't work well in JSDOM)
jest.mock("@/components/ui/sheet", () => ({
  Sheet: ({ children, open }: { children: React.ReactNode; open?: boolean }) =>
    open ? <div data-testid="sheet">{children}</div> : null,
  SheetContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetDescription: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe("Login Page Accessibility", () => {
  it("login input has accessible attributes for snapshot selectors", async () => {
    render(<WelcomePage />);

    // Click login button to open auth sheet
    const loginButton = screen.getByText("登录");
    await userEvent.click(loginButton);

    // Input must be findable by standard selectors
    const input = await screen.findByPlaceholderText(/私有密钥/i);
    expect(input).toBeInTheDocument();

    // Must have id for label association
    expect(input).toHaveAttribute("id");

    // Must have aria-label for screen readers
    expect(input).toHaveAttribute("aria-label");

    // Must have data-testid for E2E tests
    expect(input).toHaveAttribute("data-testid");
  });
});
