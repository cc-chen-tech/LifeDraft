/**
 * stores/useSceneImageStore.ts Tests
 * Tests for scene image state management
 *
 * ★ 关键测试场景：跨周次同轮次图片不混淆
 */

import { useSceneImageStore } from '@/stores/useSceneImageStore';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

describe('useSceneImageStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    useSceneImageStore.setState({
      roundSceneImages: [],
      currentRoundSceneImage: null,
      eventSceneImage: null,
      resultSceneImage: null,
      isLoadingRoundSceneImage: false,
      isRegeneratingRoundScene: false,
      roundSceneRegenerateError: null,
      historySceneImage: null,
      isLoadingHistoryImage: false,
      isGeneratingHistoryImage: false,
      isRegeneratingHistoryImage: false,
    });
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  describe('fetchAllRoundSceneImages - 跨周次场景测试', () => {
    /**
     * ★ 关键测试：跨周次同轮次图片不混淆
     * 
     * 场景：第1周第0轮有图片A，第2周第0轮有图片B
     * 当用户处于第2周第0轮时，应该显示图片B，而不是图片A
     */
    it('should not mix up scene images across different weeks with same round', async () => {
      // 准备数据：第1周第0轮和第2周第0轮都有场景图片
      const mockScenes = [
        {
          scene_id: 1,
          week: 0, // 第1周
          round_number: 0,
          stage: 'result',
          image_url: 'http://example.com/week1-round0.png',
          scene_description: '第1周第0轮场景',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
        {
          scene_id: 2,
          week: 1, // 第2周
          round_number: 0,
          stage: 'result',
          image_url: 'http://example.com/week2-round0.png',
          scene_description: '第2周第0轮场景',
          referenced_images: [],
          created_at: '2024-01-02T00:00:00Z',
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        scenes: mockScenes,
        total: 2,
      }));

      // 用户处于第2周（week=1）第0轮
      await useSceneImageStore.getState().fetchAllRoundSceneImages(1, 0, 1);

      const state = useSceneImageStore.getState();

      // 应该返回第2周的图片，而不是第1周的
      expect(state.currentRoundSceneImage).not.toBeNull();
      expect(state.currentRoundSceneImage?.scene_id).toBe(2);
      expect(state.currentRoundSceneImage?.week).toBe(1);
      expect(state.currentRoundSceneImage?.image_url).toBe('http://example.com/week2-round0.png');
      expect(state.currentRoundSceneImage?.scene_description).toBe('第2周第0轮场景');
    });

    /**
     * ★ 关键测试：当前周次没有图片时不应显示其他周次的图片
     */
    it('should return null when current week has no scene image', async () => {
      // 准备数据：只有第1周第0轮有图片
      const mockScenes = [
        {
          scene_id: 1,
          week: 0, // 第1周
          round_number: 0,
          stage: 'result',
          image_url: 'http://example.com/week1-round0.png',
          scene_description: '第1周第0轮场景',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        scenes: mockScenes,
        total: 1,
      }));

      // 用户处于第2周（week=1）第0轮，但该周次没有图片
      await useSceneImageStore.getState().fetchAllRoundSceneImages(1, 0, 1);

      const state = useSceneImageStore.getState();

      // 应该返回 null，而不是显示第1周的图片
      expect(state.currentRoundSceneImage).toBeNull();
      expect(state.resultSceneImage).toBeNull();
    });

    /**
     * 测试：正确区分 event 和 result 阶段的图片
     */
    it('should correctly separate event and result stage images', async () => {
      const mockScenes = [
        {
          scene_id: 1,
          week: 0,
          round_number: 0,
          stage: 'event',
          image_url: 'http://example.com/event.png',
          scene_description: '事件场景',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
        {
          scene_id: 2,
          week: 0,
          round_number: 0,
          stage: 'result',
          image_url: 'http://example.com/result.png',
          scene_description: '结果场景',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        scenes: mockScenes,
        total: 2,
      }));

      await useSceneImageStore.getState().fetchAllRoundSceneImages(1, 0, 0);

      const state = useSceneImageStore.getState();

      expect(state.eventSceneImage?.scene_id).toBe(1);
      expect(state.resultSceneImage?.scene_id).toBe(2);
    });

    /**
     * 测试：多周次多轮次的复杂场景
     */
    it('should handle multiple weeks and rounds correctly', async () => {
      const mockScenes = [
        // 第1周
        { scene_id: 1, week: 0, round_number: 0, stage: 'result', image_url: 'w1r0.png', scene_description: '', referenced_images: [], created_at: '' },
        { scene_id: 2, week: 0, round_number: 1, stage: 'result', image_url: 'w1r1.png', scene_description: '', referenced_images: [], created_at: '' },
        // 第2周
        { scene_id: 3, week: 1, round_number: 0, stage: 'result', image_url: 'w2r0.png', scene_description: '', referenced_images: [], created_at: '' },
        { scene_id: 4, week: 1, round_number: 1, stage: 'result', image_url: 'w2r1.png', scene_description: '', referenced_images: [], created_at: '' },
      ];

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        scenes: mockScenes,
        total: 4,
      }));

      // 测试第2周第1轮
      await useSceneImageStore.getState().fetchAllRoundSceneImages(1, 1, 1);

      const state = useSceneImageStore.getState();
      expect(state.currentRoundSceneImage?.scene_id).toBe(4);
      expect(state.roundSceneImages).toHaveLength(4);
    });
  });

  describe('fetchRoundSceneImage', () => {
    it('should fetch scene image by stage', async () => {
      const mockScene = {
        scene_id: 1,
        week: 0,
        round_number: 0,
        stage: 'event',
        image_url: 'http://example.com/scene.png',
        scene_description: '测试场景',
        referenced_images: [],
        created_at: '2024-01-01T00:00:00Z',
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockScene));

      await useSceneImageStore.getState().fetchRoundSceneImage(1, 0, 0, 'event');

      expect(global.fetch).toHaveBeenCalledWith('/api/images/scene/1/0?stage=event&week=0', expect.objectContaining({ credentials: 'include' }));
      
      const state = useSceneImageStore.getState();
      expect(state.eventSceneImage?.scene_id).toBe(1);
      // ★ fetchRoundSceneImage 不设置 currentRoundSceneImage
      expect(state.currentRoundSceneImage).toBeNull();
    });

    it('should handle 404 error gracefully', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(404));

      await useSceneImageStore.getState().fetchRoundSceneImage(1, 0, 0);

      const state = useSceneImageStore.getState();
      expect(state.isLoadingRoundSceneImage).toBe(false);
    });

    it('polls after 202 generation until the generated scene is available', async () => {
      jest.useFakeTimers();
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse({ detail: 'processing' }, 202))
        .mockResolvedValueOnce(jsonResponse({
          scene_id: 99,
          week: 0,
          round_number: 0,
          stage: 'result',
          image_url: 'http://example.com/generated.png',
          scene_description: '后台生成完成的场景',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        }));

      const promise = useSceneImageStore.getState().fetchRoundSceneImage(1, 0, 0, 'result');

      await Promise.resolve();
      expect(useSceneImageStore.getState().isLoadingRoundSceneImage).toBe(true);

      await jest.advanceTimersByTimeAsync(5000);
      await promise;

      const state = useSceneImageStore.getState();
      expect(state.isLoadingRoundSceneImage).toBe(false);
      expect(state.resultSceneImage?.scene_id).toBe(99);
      expect(global.fetch).toHaveBeenCalledTimes(2);
      jest.useRealTimers();
    });

    it('clears stale event scene and does not relabel an old week-0 image as current week', async () => {
      useSceneImageStore.setState({
        eventSceneImage: {
          scene_id: 10,
          week: 0,
          round_number: 0,
          stage: 'event',
          image_url: 'http://example.com/week1-subway.png',
          scene_description: '第1周地铁站',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        },
        roundSceneImages: [{
          scene_id: 10,
          week: 0,
          round_number: 0,
          stage: 'event',
          image_url: 'http://example.com/week1-subway.png',
          scene_description: '第1周地铁站',
          referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        }],
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        scene_id: 10,
        week: 0,
        round_number: 0,
        stage: 'event',
        image_url: 'http://example.com/week1-subway.png',
        scene_description: '第1周地铁站',
        referenced_images: [],
        created_at: '2024-01-01T00:00:00Z',
      }));

      await useSceneImageStore.getState().fetchRoundSceneImage(1, 0, 3, 'event');

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/images/scene/1/0?stage=event&week=3',
        expect.objectContaining({ credentials: 'include' })
      );
      const state = useSceneImageStore.getState();
      expect(state.eventSceneImage).toBeNull();
      expect(state.roundSceneImages).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ scene_id: 10, week: 0, round_number: 0, stage: 'event' }),
        ])
      );
      expect(state.roundSceneImages).not.toEqual(
        expect.arrayContaining([
          expect.objectContaining({ scene_id: 10, week: 3, round_number: 0, stage: 'event' }),
        ])
      );
    });

    /**
     * ★ 关键测试：并发请求去重
     * 同一参数并发调用时，只应发一次 API 请求
     */
    it('should deduplicate concurrent requests with same parameters', async () => {
      // Resolve with proper Response so fetchWithRetry can process it
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        scene_id: 1, week: 0, round_number: 0, stage: 'result',
        image_url: 'http://example.com/scene.png',
        scene_description: '测试场景', referenced_images: [],
        created_at: '2024-01-01T00:00:00Z',
      }));

      const store = useSceneImageStore.getState();

      await Promise.all([
        store.fetchRoundSceneImage(1, 0, 0),
        store.fetchRoundSceneImage(1, 0, 0),
        store.fetchRoundSceneImage(1, 0, 0),
      ]);

      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Verify scene images were loaded
      const state = useSceneImageStore.getState();
      expect(state.resultSceneImage).not.toBeNull();
      expect(state.resultSceneImage?.scene_id).toBe(1);
    });

    /**
     * ★ 测试：不同参数的调用不应被去重
     */
    it('should fetch different images for different parameters', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(jsonResponse({
          scene_id: 1, week: 0, round_number: 0, stage: 'result',
          image_url: 'http://example.com/scene1.png',
          scene_description: '场景1', referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        }))
        .mockResolvedValueOnce(jsonResponse({
          scene_id: 2, week: 0, round_number: 1, stage: 'result',
          image_url: 'http://example.com/scene2.png',
          scene_description: '场景2', referenced_images: [],
          created_at: '2024-01-01T00:00:00Z',
        }));

      const store = useSceneImageStore.getState();

      await store.fetchRoundSceneImage(1, 0, 0);
      await store.fetchRoundSceneImage(1, 1, 0);

      // Each call fetches the correct scene
      const state = useSceneImageStore.getState();
      expect(state.roundSceneImages.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('addRoundSceneImage', () => {
    it('should add new scene image to list', () => {
      const newScene = {
        scene_id: 1,
        week: 0,
        round_number: 0,
        stage: 'result',
        image_url: 'http://example.com/scene.png',
        scene_description: '测试场景',
        referenced_images: [],
        created_at: '2024-01-01T00:00:00Z',
      };

      useSceneImageStore.getState().addRoundSceneImage(newScene);

      const state = useSceneImageStore.getState();
      expect(state.roundSceneImages).toHaveLength(1);
      expect(state.roundSceneImages[0].scene_id).toBe(1);
    });

    it('should update existing scene image with same week/round/stage', () => {
      const scene1 = {
        scene_id: 1,
        week: 0,
        round_number: 0,
        stage: 'result',
        image_url: 'http://example.com/old.png',
        scene_description: '旧场景',
        referenced_images: [],
        created_at: '2024-01-01T00:00:00Z',
      };

      const scene2 = {
        scene_id: 2,
        week: 0,
        round_number: 0,
        stage: 'result',
        image_url: 'http://example.com/new.png',
        scene_description: '新场景',
        referenced_images: [],
        created_at: '2024-01-02T00:00:00Z',
      };

      useSceneImageStore.getState().addRoundSceneImage(scene1);
      useSceneImageStore.getState().addRoundSceneImage(scene2);

      const state = useSceneImageStore.getState();
      expect(state.roundSceneImages).toHaveLength(1);
      expect(state.roundSceneImages[0].scene_id).toBe(2);
      expect(state.roundSceneImages[0].image_url).toBe('http://example.com/new.png');
    });

    /**
     * ★ 关键测试：不同周次的同轮次同阶段应该作为不同条目
     */
    it('should treat same round/stage but different week as separate entries', () => {
      const sceneWeek1 = {
        scene_id: 1,
        week: 0, // 第1周
        round_number: 0,
        stage: 'result',
        image_url: 'http://example.com/week1.png',
        scene_description: '第1周场景',
        referenced_images: [],
        created_at: '2024-01-01T00:00:00Z',
      };

      const sceneWeek2 = {
        scene_id: 2,
        week: 1, // 第2周
        round_number: 0,
        stage: 'result',
        image_url: 'http://example.com/week2.png',
        scene_description: '第2周场景',
        referenced_images: [],
        created_at: '2024-01-02T00:00:00Z',
      };

      useSceneImageStore.getState().addRoundSceneImage(sceneWeek1);
      useSceneImageStore.getState().addRoundSceneImage(sceneWeek2);

      const state = useSceneImageStore.getState();
      // 应该有两个独立的条目
      expect(state.roundSceneImages).toHaveLength(2);
    });
  });

  describe('fetchHistorySceneImage', () => {
    it('should fetch history scene image with correct week and round', async () => {
      const mockScene = {
        scene_id: 1,
        week: 0,
        round_number: 1,
        stage: 'result',
        image_url: 'http://example.com/history.png',
        scene_description: '历史场景',
        referenced_images: [],
        created_at: '2024-01-01T00:00:00Z',
      };

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockScene));

      await useSceneImageStore.getState().fetchHistorySceneImage(1, 0, 1);

      expect(global.fetch).toHaveBeenCalledWith('/api/images/scene/1/1?week=0', expect.objectContaining({ credentials: 'include' }));
      
      const state = useSceneImageStore.getState();
      expect(state.historySceneImage?.scene_id).toBe(1);
    });
  });
});
