/**
 * Welcome Page Tests
 * Tests all interactive elements on the welcome/home page
 */
import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WelcomePage from '@/app/page';
import { useUserStore } from '@/stores/useUserStore';
import { useGameStore } from '@/stores/useGameStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';
import * as utils from '@/lib/utils';

// Mock useRouter
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
  }),
}));

const USER_METHODS = ['register', 'login', 'logout', 'fetchMe'] as const;
const GAME_METHODS = ['resetCreation', 'fetchSavedGames', 'fetchPresets', 'setGameSession', 'setCreationStep', 'nextCreationStep', 'prevCreationStep', 'updateCharacterSetting', 'setPlayerName', 'setLifeVision', 'loadGameState', 'setOpeningStory'] as const;

type UserStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useUserStore, (typeof USER_METHODS)[number]>>;
type GameStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof GAME_METHODS)[number]>>;

function setupDefaultState() {
  useUserStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
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
    userSpy.spies.fetchMe.mockImplementation(() => new Promise(() => {}));
  });

  afterEach(() => {
    userSpy.restore();
    gameSpy.restore();
  });

  describe('Page rendering', () => {
    it('renders the lowercase story101 brand and keeps the Chinese name descriptive', () => {
      const { container } = render(<WelcomePage />);

      expect(screen.getByRole('heading', { level: 1, name: 'story101' })).toHaveClass('font-brand');
      expect(screen.getByText('人生草稿本')).toBeInTheDocument();
      expect(screen.queryByText('Story Life')).not.toBeInTheDocument();
      expect(screen.queryByText(/AI驱动/)).not.toBeInTheDocument();
      expect(container.querySelector('[class*="gradient"], [class*="glow"]')).toBeNull();
    });

    it('keeps the main actions in one reading surface with explicit hierarchy and touch sizes', () => {
      const { container } = render(<WelcomePage />);
      const surfaces = container.querySelectorAll('[data-slot="surface"][data-variant="reading"]');
      expect(surfaces).toHaveLength(1);

      const surface = surfaces[0] as HTMLElement;
      const newGame = within(surface).getByRole('button', { name: /新游戏/i });
      const loadGame = within(surface).getByRole('button', { name: /加载存档/i });
      const presets = within(surface).getByRole('button', { name: /角色预设/i });

      expect(newGame).toHaveAttribute('data-variant', 'default');
      expect(loadGame).toHaveAttribute('data-variant', 'narrative');
      expect(presets).toHaveAttribute('data-variant', 'narrative');
      for (const action of [newGame, loadGame, presets]) {
        expect(action).toHaveAttribute('data-size', 'touch');
      }
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
    });

    it('gives the unauthenticated portal actions touch-sized controls', () => {
      render(<WelcomePage />);

      expect(screen.getByRole('button', { name: '登录' })).toHaveAttribute('data-size', 'touch');
      expect(screen.getByRole('button', { name: '注册' })).toHaveAttribute('data-size', 'touch');
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
      expect(screen.getByRole('dialog', { name: '创建账户' })).toBeInTheDocument();
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
    it('uses a real required form field with a visible label and description', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: '注册' }));

      const form = await screen.findByRole('form', { name: '创建账户' });
      const input = within(form).getByRole('textbox', { name: '显示名称' });
      const description = within(form).getByText('将在首页这样称呼你');

      expect(input).toBeRequired();
      expect(input).toHaveAttribute('aria-invalid', 'false');
      expect(input).toHaveAttribute('aria-describedby', expect.stringContaining(description.id));
      expect(within(form).getByRole('button', { name: '创建账户' })).toHaveAttribute('type', 'submit');
    });

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
    it('uses a real required form field with a visible label and description', async () => {
      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: '登录' }));

      const form = await screen.findByRole('form', { name: '登录账户' });
      const input = within(form).getByRole('textbox', { name: '私有密钥' });
      const description = within(form).getByText('使用注册时保存的唯一密钥');

      expect(input).toBeRequired();
      expect(input).toHaveAttribute('aria-invalid', 'false');
      expect(input).toHaveAttribute('aria-describedby', expect.stringContaining(description.id));
      expect(within(form).getByRole('button', { name: '登录' })).toHaveAttribute('type', 'submit');
    });

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

    it('associates a single alert with the field on login failure', async () => {
      userSpy.spies.login.mockRejectedValue(new Error('Invalid key'));

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByText('登录'));
      const input = screen.getByRole('textbox', { name: '私有密钥' });
      await user.type(input, 'bad-key');
      await user.click(screen.getByRole('button', { name: '登录' }));

      const alert = await screen.findByRole('alert');
      expect(screen.getAllByRole('alert')).toHaveLength(1);
      expect(alert).toHaveTextContent('Invalid key');
      expect(input).toHaveAttribute('aria-invalid', 'true');
      const describedByTokens = input.getAttribute('aria-describedby')?.split(/\s+/) ?? [];
      expect(describedByTokens).toContain('private-id-input-description');
      expect(describedByTokens).toContain('private-id-input-server-error');

      const errorElement = document.getElementById('private-id-input-server-error');
      expect(errorElement).not.toBeNull();
      expect(errorElement).toContainElement(alert);
    });

    it('marks the form busy and disables its controls while login is pending', async () => {
      let resolveLogin: (value: { user_id: number; display_name: string }) => void = () => {};
      userSpy.spies.login.mockImplementation(() => new Promise((resolve) => {
        resolveLogin = resolve;
      }));

      const user = userEvent.setup();
      render(<WelcomePage />);

      await user.click(screen.getByRole('button', { name: '登录' }));
      const form = screen.getByRole('form', { name: '登录账户' });
      const input = within(form).getByRole('textbox', { name: '私有密钥' });
      await user.type(input, 'test-key');
      await user.click(within(form).getByRole('button', { name: '登录' }));

      expect(form).toHaveAttribute('aria-busy', 'true');
      expect(input).toBeDisabled();
      expect(within(form).getByRole('button', { name: '登录' })).toBeDisabled();
      expect(userSpy.spies.login).toHaveBeenCalledTimes(1);

      resolveLogin({ user_id: 1, display_name: 'TestUser' });
      await waitFor(() => expect(screen.queryByRole('form', { name: '登录账户' })).not.toBeInTheDocument());
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

      const newGameLink = screen.getByRole('button', { name: /新游戏/i });
      newGameLink.addEventListener('click', (event) => event.preventDefault(), { once: true });
      await user.click(newGameLink);

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

  describe('Session recovery and prefetch', () => {
    it('validates the session once and keeps both authenticated prefetch calls', async () => {
      useUserStore.setState({
        isAuthenticated: true,
        user: {
          user_id: 1,
          display_name: 'Test User',
          public_id: 'pub-123',
        },
      });
      userSpy.spies.fetchMe.mockResolvedValue(undefined);

      render(<WelcomePage />);

      await waitFor(() => expect(userSpy.spies.fetchMe).toHaveBeenCalledTimes(1));
      await waitFor(() => {
        expect(gameSpy.spies.fetchSavedGames).toHaveBeenCalledTimes(1);
        expect(gameSpy.spies.fetchPresets).toHaveBeenCalledTimes(1);
      });
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
    it('announces the one-time warning and copy success in one status region', async () => {
      const copySpy = jest.spyOn(utils, 'copyToClipboard').mockResolvedValue(true);
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

      const warning = screen.getByRole('status');
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(warning).toHaveTextContent('此密钥仅显示一次，丢失后无法找回');

      const copyButton = screen.getByRole('button', { name: '复制私有密钥' });
      expect(copyButton).toHaveAttribute('data-size', 'icon-touch');
      await user.click(copyButton);

      await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('私有密钥已复制'));
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(copySpy).toHaveBeenCalledTimes(1);
      expect(copySpy).toHaveBeenCalledWith('priv-copy-test-123');
      copySpy.mockRestore();
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
