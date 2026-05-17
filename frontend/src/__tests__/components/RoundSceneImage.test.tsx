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
      render(<RoundSceneImageDisplay {...defaultProps} isLoading={true} />);

      expect(screen.getByText('正在生成场景插画...')).toBeInTheDocument();
    });
  });

  describe('no image state', () => {
    it('shows placeholder when no image', () => {
      render(<RoundSceneImageDisplay {...defaultProps} />);

      expect(screen.getByText('暂无场景插画')).toBeInTheDocument();
      expect(screen.getByText('生成场景插画')).toBeInTheDocument();
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
      week: 0,
      round_number: 1,
      stage: 'event',
      image_url: 'http://example.com/scene.png',
      scene_description: 'A beautiful scene',
      referenced_images: [],
      created_at: '2024-01-01',
    };

    it('displays scene image', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      expect(screen.getByRole('img')).toBeInTheDocument();
      expect(screen.getByText('第 1 轮')).toBeInTheDocument();
    });

    it('shows scene description', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      expect(screen.getByText('A beautiful scene')).toBeInTheDocument();
    });

    it('calls onRefresh when refresh button clicked', () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      fireEvent.click(screen.getByText('刷新'));
      expect(mockOnRefresh).toHaveBeenCalled();
    });

    it('shows regenerate input when regenerate button clicked', async () => {
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      fireEvent.click(screen.getByText('重生成'));

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/让场景更明亮/)).toBeInTheDocument();
      });
    });

    it('calls onRegenerate with prompt', async () => {
      mockOnRegenerate.mockResolvedValue(undefined);
      render(
        <RoundSceneImageDisplay {...defaultProps} sceneImage={mockSceneImage as any} />
      );

      // Open regenerate input
      fireEvent.click(screen.getByText('重生成'));

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
