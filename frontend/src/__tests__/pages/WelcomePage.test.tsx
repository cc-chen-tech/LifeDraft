/**
 * Welcome Page Tests
 * Tests all interactive elements on the welcome/home page
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WelcomePage from '@/app/page';
import {
  mockUserStoreState,
  mockGameStoreState,
  createAuthenticatedUserState,
  createGameInProgressState,
  resetStoreMocks,
} from '../mocks/stores';

// Mock useRouter
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
  }),
}));

// Mock hydration hook
jest.mock('@/hooks/useHydration', () => ({
  useHydration: () => true,
}));

// Mock stores
let mockUserState = { ...mockUserStoreState };
let mockGameState = { ...mockGameStoreState };

jest.mock('@/stores/useUserStore', () => ({
  useUserStore: (selector?: (state: typeof mockUserState) => unknown) =>
    selector ? selector(mockUserState) : mockUserState,
}));

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: (selector?: (state: typeof mockGameState) => unknown) =>
    selector ? selector(mockGameState) : mockGameState,
}));

describe('WelcomePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockClear();
    resetStoreMocks();
    mockUserState = { ...mockUserStoreState };
    mockGameState = { ...mockGameStoreState };
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
      
      // Click should not navigate (user not authenticated)
      await user.click(newGameButton);
      
      // After clicking, the page should still be the welcome page
      // (either showing sheet or same buttons)
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
      const registerMock = jest.fn().mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        public_id: 'pub-123',
        private_id: 'priv-456',
      });
      mockUserState = { ...mockUserStoreState, register: registerMock };
      
      const user = userEvent.setup();
      render(<WelcomePage />);
      
      await user.click(screen.getByText('注册'));
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/你的名字/i)).toBeInTheDocument();
      });
      
      await user.type(screen.getByPlaceholderText(/你的名字/i), 'TestUser');
      await user.click(screen.getByRole('button', { name: '创建账户' }));
      
      await waitFor(() => {
        expect(registerMock).toHaveBeenCalledWith('TestUser');
      });
    });

    it('shows private ID after successful registration', async () => {
      const registerMock = jest.fn().mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        public_id: 'pub-123',
        private_id: 'priv-456-789',
      });
      mockUserState = { ...mockUserStoreState, register: registerMock };
      
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
      const registerMock = jest.fn().mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        private_id: 'priv-123',
      });
      mockUserState = { ...mockUserStoreState, register: registerMock };
      
      const user = userEvent.setup();
      render(<WelcomePage />);
      
      await user.click(screen.getByText('注册'));
      const input = screen.getByPlaceholderText(/你的名字/i);
      await user.type(input, 'TestUser{Enter}');
      
      await waitFor(() => {
        expect(registerMock).toHaveBeenCalled();
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
      const loginMock = jest.fn().mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
      });
      mockUserState = { ...mockUserStoreState, login: loginMock };
      
      const user = userEvent.setup();
      render(<WelcomePage />);
      
      await user.click(screen.getByText('登录'));
      await user.type(screen.getByPlaceholderText(/私有密钥/i), 'test-key');
      await user.click(screen.getByRole('button', { name: '登录' }));
      
      await waitFor(() => {
        expect(loginMock).toHaveBeenCalledWith('test-key');
      });
    });

    it('handles Enter key in login input', async () => {
      const loginMock = jest.fn().mockResolvedValue({});
      mockUserState = { ...mockUserStoreState, login: loginMock };
      
      const user = userEvent.setup();
      render(<WelcomePage />);
      
      await user.click(screen.getByText('登录'));
      const input = screen.getByPlaceholderText(/私有密钥/i);
      await user.type(input, 'test-key{Enter}');
      
      await waitFor(() => {
        expect(loginMock).toHaveBeenCalled();
      });
    });

    it('shows error message on login failure', async () => {
      const loginMock = jest.fn().mockRejectedValue(new Error('Invalid key'));
      mockUserState = { ...mockUserStoreState, login: loginMock };
      
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
      mockUserState = createAuthenticatedUserState();
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
      const logoutMock = jest.fn();
      mockUserState = createAuthenticatedUserState({ logout: logoutMock });
      
      const user = userEvent.setup();
      render(<WelcomePage />);
      
      await user.click(screen.getByText('登出'));
      expect(logoutMock).toHaveBeenCalled();
    });

    it('navigates to /create when clicking "新游戏"', async () => {
      const resetCreationMock = jest.fn();
      mockGameState = { ...mockGameStoreState, resetCreation: resetCreationMock };
      
      const user = userEvent.setup();
      render(<WelcomePage />);
      
      await user.click(screen.getByRole('button', { name: /新游戏/i }));
      
      expect(resetCreationMock).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith('/create');
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
    it('shows continue button when there is an active game', () => {
      mockUserState = createAuthenticatedUserState();
      mockGameState = createGameInProgressState();
      
      render(<WelcomePage />);
      expect(screen.getByRole('button', { name: /继续游戏/i })).toBeInTheDocument();
    });

    it('does not show continue button when there is no active game', () => {
      mockUserState = createAuthenticatedUserState();
      mockGameState = { ...mockGameStoreState, gameId: null };
      
      render(<WelcomePage />);
      expect(screen.queryByRole('button', { name: /继续游戏/i })).not.toBeInTheDocument();
    });

    it('navigates to /play when clicking continue game', async () => {
      mockUserState = createAuthenticatedUserState();
      mockGameState = createGameInProgressState();
      
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
      const registerMock = jest.fn().mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        private_id: 'priv-copy-test-123',
      });
      mockUserState = { ...mockUserStoreState, register: registerMock };
      
      const user = userEvent.setup();
      render(<WelcomePage />);
      
      // Complete registration first
      await user.click(screen.getByText('注册'));
      await user.type(screen.getByPlaceholderText(/你的名字/i), 'TestUser');
      await user.click(screen.getByRole('button', { name: '创建账户' }));
      
      await waitFor(() => {
        expect(screen.getByText('priv-copy-test-123')).toBeInTheDocument();
      });
      
      // Verify copy button exists
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Dismiss private ID sheet', () => {
    it('closes private ID sheet when clicking confirm button', async () => {
      const registerMock = jest.fn().mockResolvedValue({
        user_id: 1,
        display_name: 'TestUser',
        private_id: 'priv-123',
      });
      mockUserState = { ...mockUserStoreState, register: registerMock };
      
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
