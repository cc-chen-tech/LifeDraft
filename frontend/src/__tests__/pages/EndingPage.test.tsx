/**
 * Tests for EndingPage component
 */
import React from 'react';
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import EndingPage from '@/app/ending/page';
import { useGameStore } from '@/stores/useGameStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

const mockPush = jest.fn();
const mockRouter = {
  push: mockPush,
  replace: jest.fn(),
};
jest.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
}));

const STORE_METHODS = ['resetGame', 'loadGameState', 'fetchSavedGames'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function renderWithCommitSnapshots(snapshots: string[]) {
  let container: HTMLElement | undefined;
  const result = render(
    <React.Profiler
      id="ending-page"
      onRender={() => {
        if (container) snapshots.push(container.textContent || '');
      }}
    >
      <EndingPage />
    </React.Profiler>,
  );
  container = result.container;
  return result;
}

function setupDefaultState() {
  useGameStore.setState({
    gameId: 123,
    playerState: { player_name: 'TestHero' },
  });
}

describe('EndingPage', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
      ending_name: '圆满人生',
      summary: 'You lived a great life.',
      ending_type: 'happy',
      achievements: { list: ['Achievement 1', 'Achievement 2'] },
      final_stats: {
        energy: 80,
        mood: 90,
        knowledge: 70,
        wealth: 100000,
        relationships: { '李明': 85, '王华': 70 },
      },
    }));
  });

  afterEach(() => {
    jest.useRealTimers();
    storeSpy.restore();
  });

  describe('Loading state', () => {
    it('shows one unified ending status without legacy loading UI', () => {
      (global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {}));

      const { container } = render(<EndingPage />);

      expect(screen.getByTestId('narrative-loading-screen')).toHaveTextContent('这一生，正在收束');
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(screen.queryByText('正在回顾你的一生...')).not.toBeInTheDocument();
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(container.querySelector('.animate-spin, .animate-pulse, [class*="skeleton"], [class*="shimmer"]')).toBeNull();
      expect(container).not.toHaveTextContent(/AI|秒|预计|fast|expert|master/i);
    });

    it('shows delayed copy once after 15 seconds', () => {
      jest.useFakeTimers();
      (global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {}));

      render(<EndingPage />);

      act(() => {
        jest.advanceTimersByTime(14_999);
      });
      expect(screen.queryByText('这一页仍在继续写作')).not.toBeInTheDocument();

      act(() => {
        jest.advanceTimersByTime(1);
      });
      expect(screen.getByText('这一页仍在继续写作')).toBeInTheDocument();
      expect(screen.getAllByRole('status')).toHaveLength(1);
    });
  });

  describe('With ending data', () => {
    it('shows ending title', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('圆满人生')).toBeInTheDocument();
      });
    });

    it('shows player name in subtitle', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText(/TestHero的人生旅程到此结束/)).toBeInTheDocument();
      });
    });

    it('shows ending story', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('You lived a great life.')).toBeInTheDocument();
      });
    });

    it('hides final numeric resource stats', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('圆满人生')).toBeInTheDocument();
      });

      expect(screen.queryByText('最终状态')).not.toBeInTheDocument();
      expect(screen.queryByText('精力')).not.toBeInTheDocument();
      expect(screen.queryByText('情绪')).not.toBeInTheDocument();
      expect(screen.queryByText('学识')).not.toBeInTheDocument();
      expect(screen.queryByText('财富')).not.toBeInTheDocument();
    });

    it('shows relationships', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('人际关系')).toBeInTheDocument();
        expect(screen.getByText('李明')).toBeInTheDocument();
        expect(screen.getByText('85/100')).toBeInTheDocument();
      });
    });

    it('shows achievements', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('人生成就')).toBeInTheDocument();
        expect(screen.getByText('Achievement 1')).toBeInTheDocument();
        expect(screen.getByText('Achievement 2')).toBeInTheDocument();
      });
    });

    it('uses one Story101 reading surface for the ready ending', async () => {
      const { container } = render(<EndingPage />);

      expect(await screen.findByRole('heading', { level: 1, name: '圆满人生' })).toBeInTheDocument();
      expect(container.querySelectorAll('[data-slot="page-transition"]')).toHaveLength(1);
      expect(
        container.querySelectorAll('[data-slot="surface"][data-variant="reading"]'),
      ).toHaveLength(1);
    });

    it('indexes and renders only normalized sections that are actually present', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        ending_name: '只留下成就的终章',
        achievements: { list: [{ name: '守住真实的一页' }] },
      }));

      render(<EndingPage />);

      const sectionIndex = await screen.findByRole('navigation', { name: '本页内容' });
      expect(within(sectionIndex).getAllByRole('link')).toHaveLength(1);
      expect(within(sectionIndex).getByRole('link', { name: '人生成就' })).toHaveAttribute(
        'href',
        '#ending-achievements',
      );
      expect(within(sectionIndex).queryByRole('link', { name: '终章正文' })).not.toBeInTheDocument();
      expect(within(sectionIndex).queryByRole('link', { name: '人际关系' })).not.toBeInTheDocument();
      expect(within(sectionIndex).queryByRole('link', { name: '人生回顾' })).not.toBeInTheDocument();
      expect(within(sectionIndex).getByRole('link', { name: '人生成就' })).toHaveClass(
        'min-h-11',
        'min-w-11',
      );
      expect(document.querySelector('pre')).toBeNull();
    });

    it('keeps ready sections flat before and after expanding the review', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        ending_name: '回望人生',
        summary: '这一页写到最后。',
        achievements: { list: ['如实生活'] },
        final_stats: { relationships: { '故友': 72 } },
        life_review: {
          personality_labels: ['清醒'],
          life_motto: '把真实的日子写下来',
          play_duration_minutes: 42,
          total_decisions: 12,
          favorite_choice_type: '平衡',
        },
      }));

      const { container } = render(<EndingPage />);
      const reviewButton = await screen.findByRole('button', { name: '查看人生回顾' });

      expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(0);
      expect(reviewButton).toHaveAttribute('aria-expanded', 'false');
      expect(reviewButton).toHaveAttribute('aria-controls', 'ending-life-review');

      fireEvent.click(reviewButton);

      expect(screen.getByTestId('life-review-card')).toBeInTheDocument();
      expect(reviewButton).toHaveAttribute('aria-expanded', 'true');
      expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(0);
      expect(screen.getByTestId('ending-share-card-scroll-region')).toContainElement(
        screen.getByText('人生草稿本 — 用 AI 书写你的故事'),
      );

      fireEvent.click(reviewButton);
      expect(reviewButton).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByTestId('life-review-card')).not.toBeInTheDocument();
    });

    it('renders explicit zero review stats, including the share preview', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        life_review: {
          play_duration_minutes: 0,
          total_decisions: 0,
        },
      }));

      render(<EndingPage />);
      fireEvent.click(await screen.findByRole('button', { name: '查看人生回顾' }));

      const reviewCard = screen.getByTestId('life-review-card');
      expect(within(reviewCard).getByText('总决策数')).toBeInTheDocument();
      expect(within(reviewCard).getByText('游戏时长(分)')).toBeInTheDocument();

      const shareRegion = screen.getByTestId('ending-share-card-scroll-region');
      expect(within(shareRegion).getByText('0分')).toBeInTheDocument();
      expect(within(shareRegion).getByText('决策数: 0')).toBeInTheDocument();
    });

    it('does not invent numeric review stats when the fields are omitted', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        life_review: { life_motto: '只写下真实拥有的部分' },
      }));

      render(<EndingPage />);
      fireEvent.click(await screen.findByRole('button', { name: '查看人生回顾' }));

      const reviewCard = screen.getByTestId('life-review-card');
      expect(within(reviewCard).queryByText('总决策数')).not.toBeInTheDocument();
      expect(within(reviewCard).queryByText('游戏时长(分)')).not.toBeInTheDocument();
      expect(screen.queryByTestId('ending-share-card-scroll-region')).not.toBeInTheDocument();
      expect(screen.queryByText('0分')).not.toBeInTheDocument();
      expect(screen.queryByText('决策数: 0')).not.toBeInTheDocument();
    });

    it('omits a missing decisions count from an otherwise valid share preview', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        life_review: {
          life_motto: '只分享真实存在的统计',
          play_duration_minutes: 7,
        },
      }));

      render(<EndingPage />);
      fireEvent.click(await screen.findByRole('button', { name: '查看人生回顾' }));

      const reviewCard = screen.getByTestId('life-review-card');
      expect(within(reviewCard).getByText('游戏时长(分)')).toBeInTheDocument();
      expect(within(reviewCard).queryByText('总决策数')).not.toBeInTheDocument();

      const shareRegion = screen.getByTestId('ending-share-card-scroll-region');
      expect(within(shareRegion).getByText('7分')).toBeInTheDocument();
      expect(within(shareRegion).queryByText(/^决策数:/)).not.toBeInTheDocument();
    });

    it('gives long normalized relationship and achievement copy a breakable row', async () => {
      const longRelationship = '这是一位名字很长需要在三百二十像素宽度下完整换行的故友';
      const longAchievement = '在很长的人生里仍然保留好奇耐心以及重新出发的勇气';
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        ending_name: '长句终章',
        achievements: { list: [longAchievement] },
        final_stats: { relationships: { [longRelationship]: 88 } },
      }));

      render(<EndingPage />);

      expect(await screen.findByText(longRelationship)).toHaveClass('min-w-0', 'break-words');
      expect(screen.getByText(longAchievement)).toHaveClass('min-w-0', 'break-words');
    });

    it.each([
      [{ summary: '只有总结也是有效结局。' }, '只有总结也是有效结局。'],
      [{ achievements: { list: ['唯一成就'] } }, '唯一成就'],
      [{ life_review: { life_motto: '保持好奇' } }, '查看人生回顾'],
      [{ final_stats: { relationships: { '故友': 42 } } }, '故友'],
    ])('accepts a meaningful partial canonical response: %p', async (response, visibleText) => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(response));

      render(<EndingPage />);

      expect(await screen.findByText(visibleText)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument();
    });

    it('ignores malformed achievements when independent ending copy is valid', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        ending_name: '安全的终章',
        achievements: { list: 'bad' },
      }));

      render(<EndingPage />);

      expect(await screen.findByText('安全的终章')).toBeInTheDocument();
      expect(screen.queryByText('人生成就')).not.toBeInTheDocument();
      expect(screen.queryByText('bad')).not.toBeInTheDocument();
    });

    it('normalizes a partial review before the user expands it', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        life_review: {
          life_motto: '保持好奇',
          personality_labels: 'bad',
          key_turning_points: { invalid: true },
          resource_curves: 'bad',
          achievement_badge_wall: 'bad',
          relationship_network: null,
          play_duration_minutes: 'bad',
          total_decisions: null,
          favorite_choice_type: { invalid: true },
        },
      }));

      render(<EndingPage />);
      fireEvent.click(await screen.findByRole('button', { name: '查看人生回顾' }));

      const reviewCard = screen.getByTestId('life-review-card');
      expect(reviewCard).toBeInTheDocument();
      expect(within(reviewCard).getByText(/“保持好奇”/)).toBeInTheDocument();
      expect(within(reviewCard).queryByText('总决策数')).not.toBeInTheDocument();
      expect(within(reviewCard).queryByText('游戏时长(分)')).not.toBeInTheDocument();
      expect(screen.queryByTestId('ending-share-card-scroll-region')).not.toBeInTheDocument();
      expect(screen.queryByText('0分')).not.toBeInTheDocument();
      expect(screen.queryByText('决策数: 0')).not.toBeInTheDocument();
      expect(screen.queryByText('bad')).not.toBeInTheDocument();
    });

    it('filters malformed relationship values without hiding valid ones', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        ending_name: '关系收束',
        final_stats: {
          relationships: {
            '故友': 72,
            '陌生人': 'high',
            '失真数值': Number.POSITIVE_INFINITY,
          },
        },
      }));

      render(<EndingPage />);

      expect(await screen.findByText('故友')).toBeInTheDocument();
      expect(screen.getByText('72/100')).toBeInTheDocument();
      expect(screen.queryByText('陌生人')).not.toBeInTheDocument();
      expect(screen.queryByText('失真数值')).not.toBeInTheDocument();
    });

    it('ignores a wrong relationships container when independent ending copy is valid', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary: '只保留安全的结局正文。',
        final_stats: { relationships: 'bad' },
      }));

      render(<EndingPage />);

      expect(await screen.findByText('只保留安全的结局正文。')).toBeInTheDocument();
      expect(screen.queryByText('人际关系')).not.toBeInTheDocument();
      expect(screen.queryByText('bad')).not.toBeInTheDocument();
    });
  });

  describe('Request ownership', () => {
    it('ignores A while B remains loading, then renders only B', async () => {
      const requestA = deferred<Response>();
      const requestB = deferred<Response>();
      (global.fetch as jest.Mock)
        .mockImplementationOnce(() => requestA.promise)
        .mockImplementationOnce(() => requestB.promise);
      const commitSnapshots: string[] = [];

      renderWithCommitSnapshots(commitSnapshots);
      await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
      commitSnapshots.length = 0;

      await act(async () => {
        useGameStore.setState({
          gameId: 456,
          playerState: { player_name: 'PlayerB' },
        });
        requestA.resolve(jsonResponse({ ending_name: 'A的终章', summary: 'A的故事' }));
        await Promise.resolve();
        await Promise.resolve();
      });

      await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
      expect(screen.getByTestId('narrative-loading-screen')).toBeInTheDocument();
      expect(screen.queryByText('A的终章')).not.toBeInTheDocument();
      expect(commitSnapshots.join('\n')).not.toContain('A的终章');

      await act(async () => {
        requestB.resolve(jsonResponse({ ending_name: 'B的终章', summary: 'B的故事' }));
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(await screen.findByText('B的终章')).toBeInTheDocument();
      expect(screen.queryByText('A的终章')).not.toBeInTheDocument();
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('never commits A content with B player state while B starts loading', async () => {
      const requestB = deferred<Response>();
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse({ ending_name: 'A已完成', summary: 'A的人生' }))
        .mockImplementationOnce(() => requestB.promise);
      const commitSnapshots: string[] = [];

      renderWithCommitSnapshots(commitSnapshots);
      expect(await screen.findByText('A已完成')).toBeInTheDocument();
      commitSnapshots.length = 0;

      act(() => {
        useGameStore.setState({
          gameId: 456,
          playerState: { player_name: 'PlayerB' },
        });
      });

      await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
      expect(screen.getByTestId('narrative-loading-screen')).toBeInTheDocument();
      expect(screen.queryByText('A已完成')).not.toBeInTheDocument();
      expect(commitSnapshots.join('\n')).not.toContain('A已完成');

      await act(async () => {
        requestB.resolve(jsonResponse({ ending_name: 'B已完成', summary: 'B的人生' }));
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(await screen.findByText('B已完成')).toBeInTheDocument();
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('Navigation buttons', () => {
    it('shows home button', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('返回首页')).toBeInTheDocument();
      });
    });

    it('shows new game button', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('开始新人生')).toBeInTheDocument();
      });
    });

    it('renders both ending actions with the touch control size', async () => {
      render(<EndingPage />);

      expect(await screen.findByRole('button', { name: '返回首页' })).toHaveAttribute(
        'data-size',
        'touch',
      );
      expect(screen.getByRole('button', { name: '开始新人生' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it('navigates home on home button click', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        const homeButton = screen.getByText('返回首页');
        fireEvent.click(homeButton);
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    it('resets game and navigates to create on new game', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        const newGameButton = screen.getByText('开始新人生');
        fireEvent.click(newGameButton);
        expect(storeSpy.spies.resetGame).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith('/create');
      });
    });
  });

  describe('No gameId', () => {
    it('returns null when no gameId', () => {
      useGameStore.setState({ gameId: null });
      const { container } = render(<EndingPage />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('API error', () => {
    it('shows an explicit failed state when the ending request rejects', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'API Error' }, 400));
      render(<EndingPage />);

      expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.getByTestId('narrative-loading-screen')).toHaveTextContent('这一生，正在收束');
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(screen.queryByText(/人生旅程到此结束/)).not.toBeInTheDocument();
    });

    it.each([null, {}])('treats an empty ending response as failed: %p', async (response) => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(response));

      render(<EndingPage />);

      expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.getAllByRole('status')).toHaveLength(1);
    });

    it.each([
      [{ message: 'temporarily unavailable' }, 'unknown response envelope'],
      [{
        ending_name: '   ',
        summary: '\n\t',
        achievements: { list: [] },
        life_review: {},
        final_stats: { relationships: {} },
      }, 'blank canonical fields'],
    ])('rejects %s: %s', async (response) => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(response));

      render(<EndingPage />);

      expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.queryByText('temporarily unavailable')).not.toBeInTheDocument();
    });

    it.each([
      { achievements: { list: 'bad' } },
      { final_stats: { relationships: 'bad' } },
    ])('rejects a response whose only canonical field is malformed: %p', async (response) => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(response));

      render(<EndingPage />);

      expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
      expect(screen.getAllByRole('status')).toHaveLength(1);
    });

    it('retries in place and renders the second successful response', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse({ message: 'API Error' }, 400))
        .mockResolvedValueOnce(jsonResponse({
          ending_name: '重试后的人生',
          summary: '终章终于完成。',
          achievements: { list: [] },
          final_stats: { relationships: {} },
        }));

      render(<EndingPage />);
      fireEvent.click(await screen.findByRole('button', { name: '重试' }));

      expect(await screen.findByText('终章终于完成。')).toBeInTheDocument();
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(mockPush).not.toHaveBeenCalled();
      expect(screen.queryByTestId('narrative-loading-screen')).not.toBeInTheDocument();
    });
  });

  describe('Partial ending data', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        ending_name: 'Simple Ending',
        summary: '',
        final_stats: null,
        achievements: null,
      }));
    });

    it('renders without final stats', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.getByText('Simple Ending')).toBeInTheDocument();
      });
      expect(screen.queryByText('最终状态')).not.toBeInTheDocument();
    });

    it('renders without achievements', async () => {
      render(<EndingPage />);
      await waitFor(() => {
        expect(screen.queryByText('人生成就')).not.toBeInTheDocument();
      });
    });
  });
});
