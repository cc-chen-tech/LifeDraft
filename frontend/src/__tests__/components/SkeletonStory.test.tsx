/**
 * components/game/SkeletonStory.tsx Tests
 * Tests for skeleton story loading component
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { SkeletonStory } from '@/components/game/SkeletonStory';

// Mock cn utility
jest.mock('@/lib/utils', () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(' '),
}));

describe('SkeletonStory', () => {
  describe('default rendering', () => {
    it('renders with default message', () => {
      render(<SkeletonStory />);

      expect(screen.getByText('正在构思故事...')).toBeInTheDocument();
    });

    it('renders skeleton placeholders', () => {
      const { container } = render(<SkeletonStory />);

      const skeletons = container.querySelectorAll('.skeleton-shimmer');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('renders loading spinner', () => {
      const { container } = render(<SkeletonStory />);

      // Loader2 icon should be present
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeTruthy();
    });
  });

  describe('custom message', () => {
    it('renders custom message', () => {
      render(<SkeletonStory message="Loading content..." />);

      expect(screen.getByText('Loading content...')).toBeInTheDocument();
    });
  });

  describe('elapsed time', () => {
    it('does not show time when elapsedSeconds is undefined', () => {
      render(<SkeletonStory />);

      expect(screen.queryByText(/已等待/)).not.toBeInTheDocument();
    });

    it('does not show time when elapsedSeconds is 0', () => {
      render(<SkeletonStory elapsedSeconds={0} />);

      expect(screen.queryByText(/已等待/)).not.toBeInTheDocument();
    });

    it('shows seconds when less than 60', () => {
      render(<SkeletonStory elapsedSeconds={30} />);

      expect(screen.getByText('已等待 30秒')).toBeInTheDocument();
    });

    it('shows minutes and seconds when 60 or more', () => {
      render(<SkeletonStory elapsedSeconds={90} />);

      expect(screen.getByText('已等待 1分30秒')).toBeInTheDocument();
    });

    it('formats multiple minutes correctly', () => {
      render(<SkeletonStory elapsedSeconds={150} />);

      expect(screen.getByText('已等待 2分30秒')).toBeInTheDocument();
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      const { container } = render(<SkeletonStory className="custom-class" />);

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });
});
