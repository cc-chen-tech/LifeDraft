/**
 * Login Page Accessibility Tests
 * Prevents: snapshot selectors failing, screen-reader incompatibility.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WelcomePage from "@/app/page";
import { useUserStore } from "@/stores/useUserStore";
import { useGameStore } from "@/stores/useGameStore";
import { spyOnStoreMethods } from "@/__tests__/helpers/store-spy";

const USER_METHODS = ['register', 'login', 'logout', 'fetchMe', 'fetchFriends', 'fetchPendingRequests', 'sendFriendRequest', 'respondToRequest', 'removeFriend'] as const;
const GAME_METHODS = ['fetchSavedGames', 'fetchPresets', 'resetCreation', 'setGameSession', 'setCreationStep', 'nextCreationStep', 'prevCreationStep', 'updateCharacterSetting', 'setPlayerName', 'setLifeVision', 'loadGameState', 'setOpeningStory'] as const;

type UserStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useUserStore, (typeof USER_METHODS)[number]>>;
type GameStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof GAME_METHODS)[number]>>;

function setupDefaultState() {
  useUserStore.setState({
    isAuthenticated: false,
    user: null,
  });
  useGameStore.setState({
    gameId: null,
  });
}

describe("Login Page Accessibility", () => {
  let userSpy: UserStoreSpy;
  let gameSpy: GameStoreSpy;

  beforeEach(() => {
    setupDefaultState();
    userSpy = spyOnStoreMethods(useUserStore, USER_METHODS);
    gameSpy = spyOnStoreMethods(useGameStore, GAME_METHODS);
  });

  afterEach(() => {
    userSpy.restore();
    gameSpy.restore();
  });

  it("login input has accessible attributes for snapshot selectors", async () => {
    render(<WelcomePage />);

    const loginButton = screen.getByText("登录");
    await userEvent.click(loginButton);

    const input = await screen.findByPlaceholderText(/私有密钥/i);
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("id");
    expect(input).toHaveAttribute("aria-label");
    expect(input).toHaveAttribute("data-testid");
  });
});
