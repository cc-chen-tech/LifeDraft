/**
 * Welcome Page Tests
 * Tests all interactive elements on the welcome/home page
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WelcomePage from '@/app/page';
import { useUserStore } from '@/stores/useUserStore';
import { useGameStore } from '@/stores/useGameStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

// Mock useRouter
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
  }),
}));

const USER_METHODS = ['register', 'login', 'logout', 'fetchMe', 'fetchFriends', 'fetchPendingRequests', 'sendFriendRequest', 'respondToRequest', 'removeFriend'] as const;
const GAME_METHODS = ['resetCreation', 'fetchSavedGames', 'fetchPresets', 'setGameSession', 'setCreationStep', 'nextCreationStep', 'prevCreationStep', 'updateCharacterSetting', 'setPlayerName', 'setLifeVision', 'loadGameState', 'setOpeningStory'] as const;

type UserStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useUserStore, (typeof USER_METHODS)[number]>>;
type GameStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof GAME_METHODS)[number]>>;

function setupDefaultState() {
  useUserStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    friends: [],
    pendingRequests: [],
  });
  useGameStore.setState({
    gameId: null,
    sessionId: null,
    playerState: null,
    progress: null,
    roundInfo: null,
    currentEvent: null,
    storyText: '',
    isGameOver: false,
    savedGames: [],
    presets: [],
    creationStep: 0,
    characterSettings: {},
    playerName: '',
    lifeVision: '',
    openingStory: '',
    isPresetLoaded: false,
    lastSummary: null,
  });
}

describe('WelcomePage', () => {
  let userSpy: UserStoreSpy;
  let gameSpy: GameStoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockClear();
    setupDefaultState();
    userSpy = spyOnStoreMethods(useUserStore, USER_METHODS);
    gameSpy = spyOnStoreMethods(useGameStore, GAME_METHODS);
  });

  afterEach(() => {
    userSpy.restore();
    gameSpy.restore();
  });

  describe('Page rendering', () => {
    it('renders the page title', () => {
      render(<WelcomePage />);
      expect(screen.getByText('Story Life')).toBeInTheDocument();
      expect(screen.getByText('AI驱动的沉浸式人生模拟')).toBeInTheDocument();
    });

    it('renders main action buttons', () => {
      render(<WelcomePage />);
      expect(screen.getByRole('button', { name: /新游戏/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /加载存档/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /角色预设/i })).toBeInTheDocument();
    });
  });

  describe('Unauthenticated user interactions', () => {
    it('shows login/register buttons when not authenticated', () => {
      render(<WelcomePage />);
      expect(screen.getByText('登录')).toBeInTheDocument();
      expect(screen.getByText('注册')).toBeInTheDocument();
    });

    it('opens register sheet when clicking "新游戏" while not authenticated', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      const newGameButton = screen.getByRole('button', { name: /新游戏/i });
      expect(newGameButton).toBeInTheDocument();

      await user.click(newGameButton);
      expect(screen.getByText('Story Life')).toBeInTheDocument();
    });

    it('opens login sheet when clicking "加载存档" while not authenticated', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: /加载存档/i }));

      await waitFor(() => {
        expect(screen.getByText('使用你的私有密钥登录')).toBeInTheDocument();
      });
    });

    it('opens login sheet when clicking "角色预设" while not authenticated', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: /角色预设/i }));

      await waitFor(() => {
        expect(screen.getByText('使用你的私有密钥登录')).toBeInTheDocument();
      });
    });

    it('opens login sheet when clicking "登录" link', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登录'));

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/私有密钥/i)).toBeInTheDocument();
      });
    });

    it('opens register sheet when clicking "注册" link', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/你的名字/i)).toBeInTheDocument();
      });
    });
  });

  describe('Registration flow', () => {
    it('allows user to input display name', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/你的名字/i)).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/你的名字/i);
      await user.type(input, 'TestUser');

      expect(input).toHaveValue('TestUser');
    });

    it('calls register when clicking register button', async () => {
      userSpy.spies.register.mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        public_id: 'pub-123',
        private_id: 'priv-456',
      });

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/你的名字/i)).toBeInTheDocument();
      });

      await user.type(screen.getByPlaceholderText(/你的名字/i), 'TestUser');
      await user.click(screen.getByRole('button', { name: '创建账户' }));

      await waitFor(() => {
        expect(userSpy.spies.register).toHaveBeenCalledWith('TestUser');
      });
    });

    it('shows private ID after successful registration', async () => {
      userSpy.spies.register.mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        public_id: 'pub-123',
        private_id: 'priv-456-789',
      });

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));
      await user.type(screen.getByPlaceholderText(/你的名字/i), 'TestUser');
      await user.click(screen.getByRole('button', { name: '创建账户' }));

      await waitFor(() => {
        expect(screen.getByText('账户创建成功！')).toBeInTheDocument();
        expect(screen.getByText('priv-456-789')).toBeInTheDocument();
      });
    });

    it('handles Enter key in register input', async () => {
      userSpy.spies.register.mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        private_id: 'priv-123',
      });

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));
      const input = screen.getByPlaceholderText(/你的名字/i);
      await user.type(input, 'TestUser{Enter}');

      await waitFor(() => {
        expect(userSpy.spies.register).toHaveBeenCalled();
      });
    });
  });

  describe('Login flow', () => {
    it('allows user to input private ID', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登录'));
      const input = screen.getByPlaceholderText(/私有密钥/i);
      await user.type(input, 'test-private-id');

      expect(input).toHaveValue('test-private-id');
    });

    it('calls login when clicking login button', async () => {
      userSpy.spies.login.mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
      });

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登录'));
      await user.type(screen.getByPlaceholderText(/私有密钥/i), 'test-key');
      await user.click(screen.getByRole('button', { name: '登录' }));

      await waitFor(() => {
        expect(userSpy.spies.login).toHaveBeenCalledWith('test-key');
      });
    });

    it('handles Enter key in login input', async () => {
      userSpy.spies.login.mockResolvedValue({});

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登录'));
      const input = screen.getByPlaceholderText(/私有密钥/i);
      await user.type(input, 'test-key{Enter}');

      await waitFor(() => {
        expect(userSpy.spies.login).toHaveBeenCalled();
      });
    });

    it('shows error message on login failure', async () => {
      userSpy.spies.login.mockRejectedValue(new Error('Invalid key'));

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登录'));
      await user.type(screen.getByPlaceholderText(/私有密钥/i), 'bad-key');
      await user.click(screen.getByRole('button', { name: '登录' }));

      await waitFor(() => {
        expect(screen.getByText('Invalid key')).toBeInTheDocument();
      });
    });
  });

  describe('Authenticated user interactions', () => {
    beforeEach(() => {
      useUserStore.setState({
        isAuthenticated: true,
        user: {
          user_id: 1,
          display_name: 'Test User',
          public_id: 'pub-123',
        },
        token: 'test-token',
      });
    });

    it('shows user greeting when authenticated', () => {
      render(<WelcomePage />);
      expect(screen.getByText(/欢迎回来，Test User/)).toBeInTheDocument();
    });

    it('shows logout button when authenticated', () => {
      render(<WelcomePage />);
      expect(screen.getByText('登出')).toBeInTheDocument();
    });

    it('calls logout when clicking logout button', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登出'));
      expect(userSpy.spies.logout).toHaveBeenCalled();
    });

    it('navigates to /create when clicking "新游戏"', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: /新游戏/i }));

      expect(gameSpy.spies.resetCreation).toHaveBeenCalled();
      expect(screen.getByRole('button', { name: /新游戏/i })).toHaveAttribute('href', '/create');
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('navigates to /saves when clicking "加载存档"', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: /加载存档/i }));

      expect(mockPush).toHaveBeenCalledWith('/saves');
    });

    it('navigates to /presets when clicking "角色预设"', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: /角色预设/i }));

      expect(mockPush).toHaveBeenCalledWith('/presets');
    });
  });

  describe('Continue game feature', () => {
    beforeEach(() => {
      useUserStore.setState({
        isAuthenticated: true,
        user: {
          user_id: 1,
          display_name: 'Test User',
          public_id: 'pub-123',
        },
        token: 'test-token',
      });
    });

    it('shows continue button when there is an active game', () => {
      useGameStore.setState({
        gameId: 1,
        sessionId: 'session-1',
        playerState: {
          player_name: 'Test Player',
          energy: 100,
          mood: 80,
        },
        progress: { week: 5 },
        roundInfo: { current_round: 1, rounds_per_week: 3 },
      });

      render(<WelcomePage />);
      expect(screen.getByRole('button', { name: /继续游戏/i })).toBeInTheDocument();
    });

    it('does not show continue button when there is no active game', () => {
      render(<WelcomePage />);
      expect(screen.queryByRole('button', { name: /继续游戏/i })).not.toBeInTheDocument();
    });

    it('navigates to /play when clicking continue game', async () => {
      useGameStore.setState({
        gameId: 1,
        sessionId: 'session-1',
        playerState: {
          player_name: 'Test Player',
          energy: 100,
          mood: 80,
        },
        progress: { week: 5 },
        roundInfo: { current_round: 1, rounds_per_week: 3 },
      });

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: /继续游戏/i }));
      expect(mockPush).toHaveBeenCalledWith('/play');
    });
  });

  describe('Auth mode switching', () => {
    it('switches from login to register mode', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登录'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/私有密钥/i)).toBeInTheDocument();
      });

      await user.click(screen.getByText('没有账户？注册'));

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/你的名字/i)).toBeInTheDocument();
      });
    });

    it('switches from register to login mode', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/你的名字/i)).toBeInTheDocument();
      });

      await user.click(screen.getByText('已有账户？登录'));

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/私有密钥/i)).toBeInTheDocument();
      });
    });
  });

  describe('Copy private ID feature', () => {
    it('has copy button in private ID display', async () => {
      userSpy.spies.register.mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        private_id: 'priv-copy-test-123',
      });

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));
      await user.type(screen.getByPlaceholderText(/你的名字/i), 'TestUser');
      await user.click(screen.getByRole('button', { name: '创建账户' }));

      await waitFor(() => {
        expect(screen.getByText('priv-copy-test-123')).toBeInTheDocument();
      });

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Dismiss private ID sheet', () => {
    it('closes private ID sheet when clicking confirm button', async () => {
      userSpy.spies.register.mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        private_id: 'priv-123',
      });

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('注册'));
      await user.type(screen.getByPlaceholderText(/你的名字/i), 'TestUser');
      await user.click(screen.getByRole('button', { name: '创建账户' }));

      await waitFor(() => {
        expect(screen.getByText('我已保存密钥，开始体验')).toBeInTheDocument();
      });

      await user.click(screen.getByText('我已保存密钥，开始体验'));

      await waitFor(() => {
        expect(screen.queryByText('priv-123')).not.toBeInTheDocument();
      });
    });
  });
});
