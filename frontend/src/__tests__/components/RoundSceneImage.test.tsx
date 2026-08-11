/**
 * components/game/RoundSceneImage.tsx Tests
 * Tests for round scene image display component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RoundSceneImageDisplay } from '@/components/game/RoundSceneImage';
import { useGameStore } from '@/stores/useGameStore';

describe('RoundSceneImageDisplay', () => {
  const mockOnRefresh = jest.fn();
  const mockOnRegenerate = jest.fn();

  const defaultProps = {
    sceneImage: null,
    isLoading: false,
    error: null as string | null,
    isRegenerating: false,
    currentRound: 1,
    onRefresh: mockOnRefresh,
    onRegenerate: mockOnRegenerate,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    useGameStore.setState({ enableSceneImage: true });
  });

  describe('when scene image is disabled', () => {
    it('returns null when enableSceneImage is false', () => {
      useGameStore.setState({ enableSceneImage: false });

      const { container } = render(<RoundSceneImageDisplay {...defaultProps} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('loading state', () => {
    it('shows loading indicator when loading and no image', () => {
      const { container } = render(
        <RoundSceneImageDisplay {...defaultProps} isLoading={true} />
      );

      expect(screen.getByText('正在生成场景插画...')).toBeInTheDocument();
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
      expect(container.querySelector('[data-slot="round-scene-state"]')).toHaveClass(
        'border-y',
        'bg-transparent',
        'shadow-none',
      );
    });
  });

  describe('no image state', () => {
    it('shows placeholder when no image', () => {
      const { container } = render(<RoundSceneImageDisplay {...defaultProps} />);

      expect(screen.getByText('暂无场景插画')).toBeInTheDocument();
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
      expect(screen.getByRole('button', { name: '生成场景插画' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it('shows a terminal error with an explicit retry action', () => {
      render(
        <RoundSceneImageDisplay
          {...defaultProps}
          error="图片生成额度暂时不可用，请稍后再试"
        />
      );

      expect(screen.getByText('图片生成额度暂时不可用，请稍后再试')).toBeVisible();
      fireEvent.click(screen.getByRole('button', { name: '重试生成场景插画' }));
      expect(mockOnRefresh).toHaveBeenCalledTimes(1);
    });

    it('calls onRefresh when generate button clicked', () => {
      render(<RoundSceneImageDisplay {...defaultProps} />);

      fireEvent.click(screen.getByText('生成场景插画'));
      expect(mockOnRefresh).toHaveBeenCalled();
    });
  });

  describe('with image', () => {
    const mockSceneImage = {
      scene_id: 1,
      round_number: 1,
      stage: 'event',
      image_url: 'http://example.com/scene.png',
      scene_description: 'A beautiful scene',
      referenced_images: [],
      created_at: '2024-01-01',
    };

    it('renders a scene generation error once with one standalone live region', () => {
      const { container } = render(
        <RoundSceneImageDisplay
          {...defaultProps}
          sceneImage={mockSceneImage}
          error="场景插画暂时无法更新"
        />,
      );

      expect(screen.getAllByText('场景插画暂时无法更新')).toHaveLength(1);
      expect(container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(1);
    });

    it('can defer scene error announcements to the page live owner', () => {
      const { container } = render(
        <RoundSceneImageDisplay
          {...defaultProps}
          sceneImage={mockSceneImage}
          error="场景插画暂时无法更新"
          announceError={false}
        />,
      );

      expect(screen.getAllByText('场景插画暂时无法更新')).toHaveLength(1);
      expect(container.querySelectorAll('[aria-live], [role="status"], [role="alert"]')).toHaveLength(0);
    });

    it('renders a flat editorial figure instead of a card or image-overlay pill', () => {
      const { container } = render(
        <RoundSceneImageDisplay
          {...defaultProps}
          sceneImage={mockSceneImage as any}
          label="事件场景"
        />
      );

      const figure = container.querySelector('figure[data-slot="round-scene-figure"]');
      expect(figure).toBeInTheDocument();
      expect(figure).toHaveClass(
        'rounded-none',
        'border-y',
        'bg-transparent',
        'shadow-none',
      );
      expect(container.querySelector('[data-slot="card"]')).toBeNull();
      expect(figure?.querySelector('figcaption')).toHaveTextContent('事件场景');
      expect(figure?.querySelector('figcaption')).toHaveTextContent('第 2 轮');

      const roundLabel = screen.getByText('第 2 轮');
      expect(roundLabel).not.toHaveClass('rounded', 'bg-black/50', 'text-white');
      expect(figure?.getAttribute('class')).not.toMatch(
        /(?:rounded-(?:lg|xl|2xl)|shadow-(?!none)|bg-card|drop-shadow)/,
      );
    });

    it('keeps every visible scene action at a 44px touch target', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      expect(screen.getByRole('button', { name: '重新生成插画' })).toHaveAttribute(
        'data-size',
        'touch',
      );
      expect(screen.getByRole('button', { name: '刷新' })).toHaveAttribute(
        'data-size',
        'touch',
      );
    });

    it('displays scene image', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      expect(screen.getByRole('img')).toBeInTheDocument();
      expect(screen.getByText('第 2 轮')).toBeInTheDocument();
    });

    it('renders a zero-based first round as the first player-facing round', () => {
      render(
        <RoundSceneImageDisplay
          {...defaultProps}
          sceneImage={{ ...mockSceneImage, round_number: 0 } as any}
        />
      );

      expect(screen.getByText('第 1 轮')).toBeInTheDocument();
      expect(screen.queryByText('第 0 轮')).not.toBeInTheDocument();
    });

    it('shows scene description', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      const description = screen.getByText('A beautiful scene');
      expect(description).toHaveClass('whitespace-normal', 'break-words');
      expect(description).not.toHaveClass('line-clamp-2', 'truncate');
    });

    it('calls onRefresh when refresh button clicked', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      fireEvent.click(screen.getByText('刷新'));
      expect(mockOnRefresh).toHaveBeenCalled();
    });

    it('shows a clear in-progress status and disables image actions while refreshing an existing scene', () => {
      render(
        <RoundSceneImageDisplay
          {...defaultProps}
          sceneImage={mockSceneImage as any}
          isLoading={true}
        />
      );

      expect(screen.getByText('正在获取或生成最新场景插画...')).toBeInTheDocument();
      expect(screen.getByText('刷新')).toBeDisabled();
      expect(screen.getByRole('button', { name: '重新生成插画' })).toBeDisabled();
    });

    it('shows regenerate input when regenerate button clicked', async () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      fireEvent.click(screen.getByRole('button', { name: '重新生成插画' }));

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: '插画修改要求' })).toHaveAttribute(
          'data-control-size',
          'touch',
        );
      });

      expect(screen.getByRole('button', { name: '确认生成' })).not.toHaveClass('text-xs');
      expect(screen.getByRole('button', { name: '取消' })).not.toHaveClass('text-xs');
    });

    it('calls onRegenerate with prompt', async () => {
      mockOnRegenerate.mockResolvedValue(undefined);
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      // Open regenerate input
      fireEvent.click(screen.getByRole('button', { name: '重新生成插画' }));

      // Enter prompt
      const input = screen.getByPlaceholderText(/让场景更明亮/);
      fireEvent.change(input, { target: { value: 'Make it brighter' } });

      // Submit
      fireEvent.click(screen.getByText('确认生成'));

      await waitFor(() => {
        expect(mockOnRegenerate).toHaveBeenCalledWith(1, 'Make it brighter');
      });
    });

    it('shows custom label', () => {
      render(
        <RoundSceneImageDisplay
          {...defaultProps}
          sceneImage={mockSceneImage as any}
          label="事件场景"
        />
      );

      expect(screen.getByText('事件场景')).toBeInTheDocument();
    });

    /**
     * ★ 关键测试：cache-busting 时间戳必须基于 created_at，而不是 Date.now()
     * 使用 Date.now() 会导致每次渲染都重新加载图片
     */
    it('should append cache-busting timestamp based on created_at', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      const img = screen.getByRole('img');
      const src = img.getAttribute('src');
      // 必须包含基于 created_at 的时间戳
      expect(src).toContain('?t=');
      expect(src).toContain('1704067200000'); // new Date('2024-01-01').getTime()
    });

    it('should not append random Date.now() timestamp when created_at is missing', () => {
      const sceneWithoutCreatedAt = {
        ...mockSceneImage,
        created_at: undefined,
      };

      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={sceneWithoutCreatedAt as any} />
      );

      const img = screen.getByRole('img');
      const src = img.getAttribute('src');
      // 不应该包含任何时间戳参数
      expect(src).not.toContain('?t=');
      expect(src).not.toContain('&t=');
      expect(src).toBe('http://example.com/scene.png');
    });
  });
});
