/**
 * Tests for session recovery in usePlayGame hook
 * 服务端会话恢复功能测试 - 用于iPad Safari等设备
 */
import { useRouter } from 'next/navigation';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

import { games } from '@/lib/api';

const mockRouter = {
  push: jest.fn(),
  replace: jest.fn(),
  back: jest.fn(),
  forward: jest.fn(),
  refresh: jest.fn(),
  prefetch: jest.fn(),
};

(useRouter as jest.Mock).mockReturnValue(mockRouter);

describe('Session Recovery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({}));
  });

  describe('Server-side recovery when localStorage fails', () => {
    it('should call getActive API when no gameId in localStorage', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 123,
        player_state: { player_name: 'RecoveredPlayer', life_vision: '', energy: 100, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 5, current_round: 1, rounds_per_week: 3, character_settings: {} },
        progress: { week: 5, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 5 },
        current_event: null,
        constraint_level: "expert",
      }));

      const result = await games.getActive();
      expect(result.game_id).toBe(123);
      expect(result.player_state.player_name).toBe('RecoveredPlayer');
    });

    it('should handle 404 when no active game on server', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'No active game found' }, 404));

      await expect(games.getActive()).rejects.toThrow('No active game found');
    });

    it('should handle network errors gracefully', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'Network error' }, 400));
      await expect(games.getActive()).rejects.toThrow('Network error');
    });

    it('should update local state after successful recovery', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 456,
        player_state: { player_name: 'Recovered', life_vision: '', energy: 80, mood: 100, knowledge: 0, wealth: 0, age: 25, week: 10, current_round: 2, rounds_per_week: 3, character_settings: {} },
        progress: { week: 10, current_round: 2, rounds_per_week: 3 },
        constraint_level: "expert",
        round_info: { current_round: 2, week: 10 },
        current_event: { event_description: 'Recovered story text', options: [{ text: 'Option 1' }] },
      }));

      const result = await games.getActive();
      expect(result.game_id).toBe(456);
      expect(result.current_event).toBeDefined();
      expect(result.current_event?.event_description).toBe('Recovered story text');
    });
  });

  describe('API integration', () => {
    it('getActive should call correct endpoint', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 1,
        player_state: { player_name: '', life_vision: '', energy: 100, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} },
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
        constraint_level: "expert",
      }));

      const result = await games.getActive();
      expect(result).toHaveProperty('game_id');

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/games/active',
        expect.objectContaining({ credentials: 'include' })
      );
    });

    it('should handle deleted game scenario', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'Active game no longer exists' }, 404));
      await expect(games.getActive()).rejects.toThrow();
    });
  });

  describe('State consistency after recovery', () => {
    it('should have consistent gameId after recovery', async () => {
      const recoveredGameId = 789;
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: recoveredGameId,
        player_state: { player_name: 'Test', life_vision: '', energy: 100, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} },
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 1 },
        current_event: null,
        constraint_level: "expert",
      }));

      const result = await games.getActive();
      expect(result.game_id).toBe(recoveredGameId);
    });

    it('should restore currentEvent if available', async () => {
      const mockEvent = { event_description: 'Test story', options: [{ text: 'Option A' }, { text: 'Option B' }] };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        game_id: 100,
        player_state: { player_name: '', life_vision: '', energy: 100, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} },
        progress: { week: 1, current_round: 1, rounds_per_week: 3 },
        constraint_level: "expert",
        round_info: { current_round: 1, week: 1 },
        current_event: mockEvent,
      }));

      const result = await games.getActive();
      expect(result.current_event).toEqual(mockEvent);
      expect(result.current_event?.options).toHaveLength(2);
    });
  });
});

describe('Redirect behavior', () => {
  it('should redirect to home when no game available', () => {
    mockRouter.replace.mockClear();
    mockRouter.replace('/');
    expect(mockRouter.replace).toHaveBeenCalledWith('/');
  });

  it('should not redirect when game is recovered', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
      game_id: 123,
      player_state: { player_name: '', life_vision: '', energy: 100, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} },
      progress: { week: 1, current_round: 1, rounds_per_week: 3 },
      round_info: { current_round: 1, week: 1 },
      current_event: null,
      constraint_level: "expert",
    }));

    const result = await games.getActive();
    expect(result.game_id).toBe(123);
  });
});
