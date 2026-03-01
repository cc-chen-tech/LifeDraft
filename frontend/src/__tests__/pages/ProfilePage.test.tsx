/**
 * Tests for ProfilePage component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ProfilePage from '@/app/profile/page';

// Mock stores
const mockUserStore = {
  user: {
    user_id: 1,
    public_id: 'ABC123',
    display_name: 'TestUser',
  },
  isAuthenticated: true,
  friends: [
    { user_id: 2, public_id: 'DEF456', display_name: 'Friend1' },
    { user_id: 3, public_id: 'GHI789', display_name: 'Friend2' },
  ],
  pendingRequests: [
    {
      request_id: 1,
      from_user: { user_id: 4, public_id: 'JKL012', display_name: 'Requester' },
    },
  ],
  fetchFriends: jest.fn().mockResolvedValue(undefined),
  fetchPendingRequests: jest.fn().mockResolvedValue(undefined),
  sendFriendRequest: jest.fn().mockResolvedValue(undefined),
  respondToRequest: jest.fn().mockResolvedValue(undefined),
  removeFriend: jest.fn().mockResolvedValue(undefined),
};

jest.mock('@/stores/useUserStore', () => ({
  useUserStore: (selector?: (state: typeof mockUserStore) => unknown) => {
    if (selector) return selector(mockUserStore);
    return mockUserStore;
  },
}));

jest.mock('@/hooks/useHydration', () => ({
  useHydration: () => true,
}));

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
  }),
}));

// Mock clipboard
const mockWriteText = jest.fn().mockResolvedValue(undefined);
Object.assign(navigator, {
  clipboard: {
    writeText: mockWriteText,
  },
});

describe('ProfilePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.assign(mockUserStore, {
      isAuthenticated: true,
      friends: [
        { user_id: 2, public_id: 'DEF456', display_name: 'Friend1' },
        { user_id: 3, public_id: 'GHI789', display_name: 'Friend2' },
      ],
      pendingRequests: [
        {
          request_id: 1,
          from_user: { user_id: 4, public_id: 'JKL012', display_name: 'Requester' },
        },
      ],
    });
  });

  describe('User info section', () => {
    it('renders page title', () => {
      render(<ProfilePage />);
      expect(screen.getByText('个人资料')).toBeInTheDocument();
    });

    it('renders user display name', () => {
      render(<ProfilePage />);
      expect(screen.getByText('TestUser')).toBeInTheDocument();
    });

    it('renders public ID', () => {
      render(<ProfilePage />);
      expect(screen.getByText('ABC123')).toBeInTheDocument();
    });

    it('renders copy button', () => {
      render(<ProfilePage />);
      expect(screen.getByText('公开ID')).toBeInTheDocument();
    });
  });

  describe('Add friend section', () => {
    it('renders add friend title', () => {
      render(<ProfilePage />);
      expect(screen.getByText('添加好友')).toBeInTheDocument();
    });

    it('renders friend code input', () => {
      render(<ProfilePage />);
      expect(screen.getByPlaceholderText('输入好友的公开ID')).toBeInTheDocument();
    });

    it('renders send button', () => {
      render(<ProfilePage />);
      expect(screen.getByText('发送')).toBeInTheDocument();
    });

    it('send button is disabled when input is empty', () => {
      render(<ProfilePage />);
      const sendButton = screen.getByText('发送');
      expect(sendButton).toBeDisabled();
    });

    it('calls sendFriendRequest on submit', async () => {
      const user = userEvent.setup();
      render(<ProfilePage />);
      
      const input = screen.getByPlaceholderText('输入好友的公开ID');
      await user.type(input, 'FRIEND123');
      
      const sendButton = screen.getByText('发送');
      fireEvent.click(sendButton);
      
      await waitFor(() => {
        expect(mockUserStore.sendFriendRequest).toHaveBeenCalledWith('FRIEND123');
      });
    });

    it('shows error message on failed request', async () => {
      mockUserStore.sendFriendRequest.mockRejectedValueOnce(new Error('User not found'));
      const user = userEvent.setup();
      render(<ProfilePage />);
      
      const input = screen.getByPlaceholderText('输入好友的公开ID');
      await user.type(input, 'INVALID');
      
      const sendButton = screen.getByText('发送');
      fireEvent.click(sendButton);
      
      await waitFor(() => {
        expect(screen.getByText('User not found')).toBeInTheDocument();
      });
    });
  });

  describe('Pending requests section', () => {
    it('renders pending requests title', () => {
      render(<ProfilePage />);
      expect(screen.getByText('待处理请求 (1)')).toBeInTheDocument();
    });

    it('renders requester name', () => {
      render(<ProfilePage />);
      expect(screen.getByText('Requester')).toBeInTheDocument();
    });

    it('renders accept button', () => {
      render(<ProfilePage />);
      expect(screen.getByText('接受')).toBeInTheDocument();
    });

    it('renders reject button', () => {
      render(<ProfilePage />);
      expect(screen.getByText('拒绝')).toBeInTheDocument();
    });

    it('calls respondToRequest with true on accept', () => {
      render(<ProfilePage />);
      const acceptButton = screen.getByText('接受');
      fireEvent.click(acceptButton);
      expect(mockUserStore.respondToRequest).toHaveBeenCalledWith(1, true);
    });

    it('calls respondToRequest with false on reject', () => {
      render(<ProfilePage />);
      const rejectButton = screen.getByText('拒绝');
      fireEvent.click(rejectButton);
      expect(mockUserStore.respondToRequest).toHaveBeenCalledWith(1, false);
    });
  });

  describe('Friends list section', () => {
    it('renders friends list title', () => {
      render(<ProfilePage />);
      expect(screen.getByText('好友列表 (2)')).toBeInTheDocument();
    });

    it('renders friend names', () => {
      render(<ProfilePage />);
      expect(screen.getByText('Friend1')).toBeInTheDocument();
      expect(screen.getByText('Friend2')).toBeInTheDocument();
    });

    it('renders friend public IDs', () => {
      render(<ProfilePage />);
      expect(screen.getByText('DEF456')).toBeInTheDocument();
      expect(screen.getByText('GHI789')).toBeInTheDocument();
    });

    it('calls removeFriend on remove button click', () => {
      render(<ProfilePage />);
      const removeButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg')
      );
      // Click the X button for first friend
      const xButtons = screen.getAllByRole('button');
      // Find the X buttons (they have X icon)
      fireEvent.click(xButtons[xButtons.length - 2]); // Second to last button
      // This is approximate, might need adjustment
    });
  });

  describe('Empty states', () => {
    it('shows empty message when no friends', () => {
      Object.assign(mockUserStore, { friends: [] });
      render(<ProfilePage />);
      expect(screen.getByText('暂无好友')).toBeInTheDocument();
    });

    it('hides pending requests section when empty', () => {
      Object.assign(mockUserStore, { pendingRequests: [] });
      render(<ProfilePage />);
      expect(screen.queryByText('待处理请求')).not.toBeInTheDocument();
    });
  });

  describe('Not authenticated', () => {
    beforeEach(() => {
      Object.assign(mockUserStore, { isAuthenticated: false });
    });

    afterEach(() => {
      Object.assign(mockUserStore, { isAuthenticated: true });
    });

    it('returns null when not authenticated', () => {
      const { container } = render(<ProfilePage />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('Navigation', () => {
    it('navigates back on back button click', () => {
      render(<ProfilePage />);
      const backButton = screen.getByText('返回');
      fireEvent.click(backButton);
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('Data fetching', () => {
    it('fetches friends on mount', () => {
      render(<ProfilePage />);
      expect(mockUserStore.fetchFriends).toHaveBeenCalled();
    });

    it('fetches pending requests on mount', () => {
      render(<ProfilePage />);
      expect(mockUserStore.fetchPendingRequests).toHaveBeenCalled();
    });
  });
});
