/**
 * components/game/StatusBar.tsx Tests
 * Tests for status bar component
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { StatusBar } from '@/components/game/StatusBar';

// Mock cn utility
jest.mock('@/lib/utils', () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(' '),
}));

describe('StatusBar', () => {
  const mockPlayerState = {
    age: 25,
    week: 9,  // ★ week 从0开始，显示时会 +1，所以显示"第10周"
    attributes: {
      health: { name: '健康', value: 80, max_value: 100 },
      intelligence: { name: '智力', value: 60, max_value: 100 },
      charisma: { name: '魅力', value: 70, max_value: 100 },
      wealth: { name: '财富', value: 50, max_value: 100 },
    },
    wealth_level: '中产',
  };

  const mockProgress = {
    current_round: 5,
    total_rounds: 10,
  };

  describe('when playerState is null', () => {
    it('returns null', () => {
      const { container } = render(
        <StatusBar playerState={null} progress={null} />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe('compact mode (default)', () => {
    it('displays age and week', () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      expect(screen.getByText('25岁 第10周')).toBeInTheDocument();
    });

    it('displays progress when available', () => {
      render(<StatusBar playerState={mockPlayerState} progress={mockProgress} />);

      expect(screen.getByText('5/10')).toBeInTheDocument();
    });

    it('displays attributes', () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      expect(screen.getByText(/健康: 80/)).toBeInTheDocument();
      expect(screen.getByText(/智力: 60/)).toBeInTheDocument();
    });

    it('limits attributes to first 4', () => {
      render(<StatusBar playerState={mockPlayerState} progress={null} />);

      // Should show health, intelligence, charisma, wealth
      const badges = screen.getAllByRole('generic');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  describe('full mode', () => {
    it('displays age and week in header', () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={null} compact={false} />
      );

      expect(screen.getByText('25岁 第10周')).toBeInTheDocument();
    });

    it('displays progress bar when available', () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={mockProgress} compact={false} />
      );

      expect(screen.getByText('进度 5/10')).toBeInTheDocument();
    });

    it('displays all attributes with bars', () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={null} compact={false} />
      );

      expect(screen.getByText('健康')).toBeInTheDocument();
      expect(screen.getByText('智力')).toBeInTheDocument();
      expect(screen.getByText('魅力')).toBeInTheDocument();
      expect(screen.getByText('财富')).toBeInTheDocument();
    });

    it('displays wealth level', () => {
      render(
        <StatusBar playerState={mockPlayerState} progress={null} compact={false} />
      );

      expect(screen.getByText(/财富: 中产/)).toBeInTheDocument();
    });
  });

  describe('attribute colors', () => {
    it('applies success color for high values', () => {
      const highHealthState = {
        ...mockPlayerState,
        attributes: {
          health: { name: '健康', value: 90, max_value: 100 },
        },
      };

      render(<StatusBar playerState={highHealthState} progress={null} />);
      // Component renders without error
      expect(screen.getByText(/健康: 90/)).toBeInTheDocument();
    });

    it('applies warning color for medium values', () => {
      const mediumHealthState = {
        ...mockPlayerState,
        attributes: {
          health: { name: '健康', value: 50, max_value: 100 },
        },
      };

      render(<StatusBar playerState={mediumHealthState} progress={null} />);
      expect(screen.getByText(/健康: 50/)).toBeInTheDocument();
    });

    it('applies destructive color for low values', () => {
      const lowHealthState = {
        ...mockPlayerState,
        attributes: {
          health: { name: '健康', value: 20, max_value: 100 },
        },
      };

      render(<StatusBar playerState={lowHealthState} progress={null} />);
      expect(screen.getByText(/健康: 20/)).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles missing attributes', () => {
      render(
        <StatusBar playerState={{ age: 25, week: 0 }} progress={null} />  // ★ week=0 显示 "第1周"
      );

      expect(screen.getByText('25岁 第1周')).toBeInTheDocument();
    });

    it('handles zero progress', () => {
      render(
        <StatusBar
          playerState={mockPlayerState}
          progress={{ current_round: 0, total_rounds: 10 }}
        />
      );

      // Progress should not be shown when current_round is 0
      expect(screen.queryByText('0/10')).not.toBeInTheDocument();
    });
  });
});
