/**
 * components/game/RoundHistoryDrawer.tsx Tests
 * Tests for round history drawer component
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RoundHistoryDrawer, RoundHistoryItem } from '@/components/game/RoundHistoryDrawer';

describe('RoundHistoryDrawer', () => {
  const mockOnOpenChange = jest.fn();
  const mockOnSelect = jest.fn();
  const mockOnBackToCurrent = jest.fn();

  const defaultHistory: RoundHistoryItem[] = [
    { week: 0, round: 0, event_description: 'Story 1', choice: 'Choice 1' },
    { week: 0, round: 1, event_description: 'Story 2', choice: 'Choice 2' },
    { week: 0, round: 2, event_description: 'Story 3', choice: 'Choice 3' },
    { week: 1, round: 0, event_description: 'Story 4', choice: 'Choice 4' },
  ];

  const defaultProps = {
    open: true,
    onOpenChange: mockOnOpenChange,
    roundHistory: defaultHistory,
    selectedIndex: null,
    onSelect: mockOnSelect,
    onBackToCurrent: mockOnBackToCurrent,
    isViewingHistory: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders drawer when open', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      expect(screen.getByText('历史回顾')).toBeInTheDocument();
      expect(screen.getByText('查看之前轮次的故事（只读模式）')).toBeInTheDocument();
    });

    it('uses the responsive drawer width above persistent sound controls', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      const content = document.querySelector('[data-slot="sheet-content"]');
      expect(content).toHaveClass(
        'w-full',
        'max-w-[min(100vw,24rem)]',
        'z-[71]',
      );
      expect(content).not.toHaveClass('w-80', 'sm:w-96', 'z-50');
    });

    it('groups rounds by week', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      expect(screen.getByText('第 1 周')).toBeInTheDocument();
      expect(screen.getByText('第 2 周')).toBeInTheDocument();
    });

    it('displays round names', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      // ★ 使用 getAllByText 因为测试数据有多个周一
      expect(screen.getAllByText('周一').length).toBeGreaterThan(0);
      expect(screen.getByText('周中')).toBeInTheDocument();
      expect(screen.getByText('周末')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no history', () => {
      render(<RoundHistoryDrawer {...defaultProps} roundHistory={[]} />);

      expect(screen.getByText('暂无历史记录')).toBeInTheDocument();
    });
  });

  describe('history items', () => {
    it('displays choice text', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      expect(screen.getByText(/选择: Choice 1/)).toBeInTheDocument();
    });

    it('displays summary when available', () => {
      const historyWithSummary: RoundHistoryItem[] = [
        { week: 0, round: 0, summary: 'Summary text' },
      ];

      render(<RoundHistoryDrawer {...defaultProps} roundHistory={historyWithSummary} />);

      expect(screen.getByText('Summary text')).toBeInTheDocument();
    });

    it('shows recorded badge when has story', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      expect(screen.getAllByText('已记录').length).toBeGreaterThan(0);
    });

    it('displays date string when available', () => {
      const historyWithDate: RoundHistoryItem[] = [
        { week: 0, round: 0, date_info: { date_string: '2024-01-01' } },
      ];

      render(<RoundHistoryDrawer {...defaultProps} roundHistory={historyWithDate} />);

      expect(screen.getByText('(2024-01-01)')).toBeInTheDocument();
    });

    it('renders rounds as flat archive rows without badge pills or nested cards', () => {
      render(
        <RoundHistoryDrawer {...defaultProps} selectedIndex={0} />
      );

      const firstRound = screen.getByRole('button', {
        name: '第 1 周 周一：阅读正文',
      });
      expect(firstRound).toHaveAttribute('data-slot', 'history-round-row');
      expect(firstRound).toHaveClass(
        'min-h-11',
        'rounded-none',
        'border-x-0',
        'border-t-0',
        'bg-transparent',
        'shadow-none',
      );
      expect(firstRound.getAttribute('class')).not.toMatch(
        /(?:rounded-(?:lg|xl|2xl)|shadow-(?!none)|bg-card|bg-primary|drop-shadow)/,
      );

      const recorded = firstRound.querySelector('[data-slot="history-recorded"]');
      expect(recorded).toHaveTextContent('已记录');
      expect(recorded).toHaveClass('text-xs');
      expect(recorded).not.toHaveClass('text-[11px]');
      expect(firstRound.querySelector('[data-slot="badge"]')).toBeNull();

      const selectedBody = document.querySelector('[data-slot="history-round-body"]');
      expect(selectedBody).toHaveClass(
        'rounded-none',
        'bg-transparent',
        'shadow-none',
        'text-sm',
      );
      expect(selectedBody).not.toHaveClass('text-xs');
      expect(selectedBody?.getAttribute('class')).not.toMatch(
        /(?:rounded-(?:md|lg|xl)|shadow-(?!none)|bg-primary|drop-shadow)/,
      );
    });
  });

  describe('interactions', () => {
    it('provides a Chinese-labelled 44px close action and preserves onOpenChange', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      const closeButton = screen.getByRole('button', { name: '关闭历史回顾' });
      expect(closeButton).toHaveAttribute('data-size', 'icon-touch');
      expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument();

      fireEvent.click(closeButton);

      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });

    it('calls onOpenChange(false) when pressing Escape', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      fireEvent.keyDown(document.body, { key: 'Escape', code: 'Escape' });

      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });

    it('uses a transparent modal overlay so keyboard focus cannot reach the reading page', async () => {
      const user = userEvent.setup();
      render(<RoundHistoryDrawer {...defaultProps} />);

      const overlay = document.querySelector('[data-slot="sheet-overlay"]');
      const content = document.querySelector('[data-slot="sheet-content"]');
      const closeButton = screen.getByRole('button', { name: '关闭历史回顾' });

      expect(overlay).toHaveClass('bg-transparent');
      expect(overlay).not.toHaveClass('pointer-events-none');
      expect(content).toHaveClass('data-[state=closed]:pointer-events-none');

      closeButton.focus();
      await user.tab({ shift: true });
      expect(document.activeElement).not.toBe(document.body);
      expect(content).toContainElement(document.activeElement as HTMLElement);
    });

    it('calls onSelect when clicking a round', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      // ★ 使用 getAllByText 因为可能有多个周一，点击第一个
      const mondayButtons = screen.getAllByText('周一');
      fireEvent.click(mondayButtons[0]);

      expect(mockOnSelect).toHaveBeenCalledWith(0);
    });

    it('closes the drawer after selecting a round so the readable story surface is exposed', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      fireEvent.click(screen.getAllByText('周一')[0]);

      expect(mockOnSelect).toHaveBeenCalledWith(0);
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });

    it('shows back button when viewing history', () => {
      render(<RoundHistoryDrawer {...defaultProps} isViewingHistory={true} />);

      expect(screen.getByRole('button', { name: '返回当前轮次' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it('calls onBackToCurrent when clicking back button', () => {
      render(<RoundHistoryDrawer {...defaultProps} isViewingHistory={true} />);

      fireEvent.click(screen.getByText('返回当前轮次'));

      expect(mockOnBackToCurrent).toHaveBeenCalled();
    });
  });

  describe('selection state', () => {
    it('highlights selected round', () => {
      render(<RoundHistoryDrawer {...defaultProps} selectedIndex={0} />);

      // The selected item should have different styling
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('shows readable selected history content instead of only the summary button', () => {
      const historyWithFullText: RoundHistoryItem[] = [
        {
          week: 0,
          round: 0,
          summary: 'Short summary only',
          event_description: 'Full historical event body that should be readable.',
          story_continuation: 'Full post-choice continuation that should stay visible.',
        },
      ];

      render(
        <RoundHistoryDrawer
          {...defaultProps}
          roundHistory={historyWithFullText}
          selectedIndex={0}
          isViewingHistory={true}
        />
      );

      expect(screen.getByText(/Full historical event body/)).toBeInTheDocument();
      expect(screen.getByText(/Full post-choice continuation/)).toBeInTheDocument();
      expect(screen.getByText('选择后的故事发展')).toBeInTheDocument();
    });
  });

  describe('footer', () => {
    it('displays total count', () => {
      render(<RoundHistoryDrawer {...defaultProps} />);

      expect(screen.getByText('共 4 轮历史记录')).toBeInTheDocument();
    });
  });
});
