/**
 * stores/useImageStore.ts Tests
 * Tests for image state management
 */

import { useImageStore } from '@/stores/useImageStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import api from '@/lib/api';

describe('useImageStore', () => {
  beforeEach(() => {
    useImageStore.getState().stopPortraitImagePolling();
    // Reset store to initial state
    useImageStore.setState({
      playerImage: null,
      playerImages: [],
      selectedImageIndex: 0,
      selectedImageId: null,
      portraitCandidates: null,
      isGeneratingImage: false,
      imageGenerationError: null,
      portraitImageJob: null,
      imageFeedback: '',
      openingIllustration: null,
      isGeneratingIllustration: false,
      illustrationError: null,
      // ★ 场景插画状态已移至 useGameStore
    });
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  describe('Player Image Actions', () => {
    describe('setPlayerImage', () => {
      it('sets player image and updates playerImages array', () => {
        const image = { image_id: 1, image_url: 'http://example.com/img.png' } as any;
        useImageStore.getState().setPlayerImage(image);

        expect(useImageStore.getState().playerImage).toBe(image);
        expect(useImageStore.getState().playerImages).toEqual([image]);
        expect(useImageStore.getState().selectedImageIndex).toBe(0);
      });

      it('clears player image when null', () => {
        useImageStore.setState({ playerImage: { image_id: 1, image_url: 'test' } as any });
        useImageStore.getState().setPlayerImage(null);

        expect(useImageStore.getState().playerImage).toBeNull();
        expect(useImageStore.getState().playerImages).toEqual([]);
      });
    });

    describe('setPlayerImages', () => {
      it('sets player images array and selects first', () => {
        const images = [
          { image_id: 1, image_url: 'url1' },
          { image_id: 2, image_url: 'url2' },
        ] as any;
        useImageStore.getState().setPlayerImages(images);

        expect(useImageStore.getState().playerImages).toEqual(images);
        expect(useImageStore.getState().playerImage).toBe(images[0]);
        expect(useImageStore.getState().selectedImageIndex).toBe(0);
      });
    });

    describe('setSelectedImageIndex', () => {
      it('updates selected index and playerImage', () => {
        const images = [
          { image_id: 1, image_url: 'url1' },
          { image_id: 2, image_url: 'url2' },
        ];
        useImageStore.setState({ playerImages: images as any });

        useImageStore.getState().setSelectedImageIndex(1);

        expect(useImageStore.getState().selectedImageIndex).toBe(1);
        expect(useImageStore.getState().playerImage).toBe(images[1]);
      });
    });

    describe('generatePlayerImage', () => {
      it('throws error without gameId', async () => {
        await expect(
          useImageStore.getState().generatePlayerImage(0, 'Test', {})
        ).rejects.toThrow('游戏ID不存在');
      });

      it('throws error without playerName', async () => {
        await expect(
          useImageStore.getState().generatePlayerImage(1, '', {})
        ).rejects.toThrow('请先输入角色姓名');
      });

      it('queues player image generation without waiting for MiniMax', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
          job_id: 9,
          game_id: 1,
          status: 'queued',
          image_id: null,
          attempt_count: 0,
        }, 202));

        await useImageStore.getState().generatePlayerImage(1, 'TestPlayer', {
          era: { era: '现代', era_name: '现代' },
          age: { age: 25 },
          gender: { gender: '男' },
        });

        expect(global.fetch).toHaveBeenCalledWith(
          '/api/images/character/generate-async',
          expect.objectContaining({ method: 'POST' })
        );
        expect(useImageStore.getState().playerImages).toEqual([]);
        expect(useImageStore.getState().isGeneratingImage).toBe(true);
        expect(useImageStore.getState().portraitImageJob).toMatchObject({ job_id: 9, status: 'queued' });
      });

      it('handles enqueue error', async () => {
        (global.fetch as jest.Mock).mockRejectedValue(new Error('API Error'));

        await expect(
          useImageStore.getState().generatePlayerImage(1, 'Test', {})
        ).rejects.toThrow('API Error');

        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });

      it('keeps the durable job pending when a polling request is temporarily disconnected', async () => {
        useImageStore.setState({
          isGeneratingImage: true,
          portraitImageJob: { job_id: 9, game_id: 1, status: 'running', image_id: null, attempt_count: 1 },
        });
        (global.fetch as jest.Mock).mockRejectedValue(new TypeError('Failed to fetch'));

        await useImageStore.getState().refreshPortraitImageJob(1);

        expect(useImageStore.getState()).toMatchObject({
          isGeneratingImage: true,
          imageGenerationError: null,
        });
      });

      it('ignores a stale portrait job response after switching games', async () => {
        let resolveFirstGame!: (response: Response) => void;
        const firstGameResponse = new Promise<Response>((resolve) => {
          resolveFirstGame = resolve;
        });
        (global.fetch as jest.Mock).mockImplementation((url: string) => {
          if (url.includes('game_id=1')) return firstGameResponse;
          if (url.includes('game_id=2')) {
            return Promise.resolve(jsonResponse({
              job_id: 22,
              game_id: 2,
              status: 'queued',
              image_id: null,
              attempt_count: 0,
            }));
          }
          throw new Error(`Unexpected URL: ${url}`);
        });

        const staleRefresh = useImageStore.getState().refreshPortraitImageJob(1);
        await useImageStore.getState().refreshPortraitImageJob(2);
        resolveFirstGame(jsonResponse({
          job_id: 11,
          game_id: 1,
          status: 'queued',
          image_id: null,
          attempt_count: 0,
        }));
        await staleRefresh;

        expect(useImageStore.getState().portraitImageJob).toMatchObject({
          job_id: 22,
          game_id: 2,
        });
      });

      it('loads the persisted image after polling reports success', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(
          jsonResponse({
            job_id: 9,
            game_id: 1,
            status: 'succeeded',
            image_id: 42,
            attempt_count: 1,
          })
        );
        (global.fetch as jest.Mock).mockResolvedValueOnce(
          jsonResponse({
            job_id: 9,
            game_id: 1,
            status: 'succeeded',
            image_id: 42,
            attempt_count: 1,
          })
        ).mockResolvedValueOnce(jsonResponse({
          images: [{ image_id: 42, image_url: 'url42', entity_key: 'player_main' }],
          total: 1,
        }));

        await useImageStore.getState().refreshPortraitImageJob(1);

        expect(useImageStore.getState()).toMatchObject({
          isGeneratingImage: false,
          imageGenerationError: null,
          playerImages: [{ image_id: 42, image_url: 'url42', entity_key: 'player_main' }],
        });
      });

      it('retries image retrieval after a successful job when the image list fails once', async () => {
        jest.useFakeTimers();
        const oldImage = { image_id: 1, game_id: 1, image_url: 'old', entity_key: 'player_main' };
        const newImage = { image_id: 42, game_id: 1, image_url: 'new', entity_key: 'player_main' };
        useImageStore.setState({ playerImages: [oldImage] as any, isGeneratingImage: true });
        const jobSpy = jest.spyOn(api.images, 'getLatestCharacterPortraitJob').mockResolvedValue({
          job_id: 9, game_id: 1, status: 'succeeded', image_id: 42, attempt_count: 1,
        });
        const imageSpy = jest.spyOn(api.images, 'listByGame')
          .mockRejectedValueOnce(new TypeError('Failed to fetch'))
          .mockResolvedValueOnce({ images: [newImage], total: 1 });

        try {
          await useImageStore.getState().refreshPortraitImageJob(1);
          expect(useImageStore.getState().playerImages).toEqual([oldImage]);
          expect(useImageStore.getState().isGeneratingImage).toBe(true);

          await jest.advanceTimersByTimeAsync(3_000);
          expect(imageSpy).toHaveBeenCalledTimes(2);
          expect(useImageStore.getState().playerImages).toEqual([newImage]);
          expect(useImageStore.getState().isGeneratingImage).toBe(false);
        } finally {
          useImageStore.getState().stopPortraitImagePolling();
          jobSpy.mockRestore();
          imageSpy.mockRestore();
          jest.useRealTimers();
        }
      });

      it('stores a safe background provider failure and allows a retry', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
          job_id: 9,
          game_id: 1,
          status: 'failed',
          image_id: null,
          attempt_count: 1,
          error_code: 'minimax_2056',
          error_message: '图片生成额度暂时不可用，请稍后再试',
        }));

        await useImageStore.getState().refreshPortraitImageJob(1);

        expect(useImageStore.getState()).toMatchObject({
          isGeneratingImage: false,
          imageGenerationError: '图片生成额度暂时不可用，请稍后再试',
          portraitImageJob: { status: 'failed', error_code: 'minimax_2056' },
        });
      });
    });

    describe('regeneratePlayerImage', () => {
      it('throws error without existing image', async () => {
        await expect(
          useImageStore.getState().regeneratePlayerImage('feedback')
        ).rejects.toThrow('没有可重新生成的图片');
      });

      it('queues regeneration and keeps the old image until the job succeeds', async () => {
        const existingImage = { image_id: 1, game_id: 1, image_url: 'old', entity_key: 'player_main' };
        const newImages = [{ image_id: 2, game_id: 1, image_url: 'new', entity_key: 'player_main' }];
        useImageStore.setState({ playerImages: [existingImage] as any });
        (global.fetch as jest.Mock).mockResolvedValueOnce(jsonResponse({
          job_id: 10, game_id: 1, status: 'queued', image_id: null, attempt_count: 0,
        }, 202)).mockResolvedValueOnce(jsonResponse({
          job_id: 10, game_id: 1, status: 'succeeded', image_id: 2, attempt_count: 1,
        })).mockResolvedValueOnce(jsonResponse({ images: newImages, total: 1 }));

        await useImageStore.getState().regeneratePlayerImage('make it better');

        expect(global.fetch).toHaveBeenCalledWith('/api/images/character/regenerate-async', expect.objectContaining({ method: 'POST' }));
        expect(useImageStore.getState().playerImages).toEqual([existingImage]);
        expect(useImageStore.getState().isGeneratingImage).toBe(true);
        await useImageStore.getState().refreshPortraitImageJob(1);
        expect(useImageStore.getState().playerImages).toEqual(newImages);
        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });

      it('handles regeneration error', async () => {
        const existingImage = { image_id: 1, game_id: 1, image_url: 'old' };
        useImageStore.setState({ playerImages: [existingImage] as any });
        (global.fetch as jest.Mock).mockRejectedValue(new Error('Regeneration failed'));

        await expect(
          useImageStore.getState().regeneratePlayerImage('feedback')
        ).rejects.toThrow('Regeneration failed');

        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });

      it('recovers a queued job when its enqueue response is lost', async () => {
        useImageStore.setState({
          playerImages: [{ image_id: 1, game_id: 1, image_url: 'old' }] as any,
        });
        (global.fetch as jest.Mock)
          .mockRejectedValueOnce(new TypeError('Failed to fetch'))
          .mockResolvedValueOnce(jsonResponse({
            job_id: 12, game_id: 1, status: 'queued', image_id: null, attempt_count: 0,
          }));

        await useImageStore.getState().regeneratePlayerImage('short hair');

        expect(useImageStore.getState()).toMatchObject({
          isGeneratingImage: true,
          imageGenerationError: null,
          portraitImageJob: { job_id: 12, status: 'queued' },
        });
        expect((global.fetch as jest.Mock).mock.calls.filter(([url]) => url === '/api/images/character/regenerate-async')).toHaveLength(1);
      });

      it('does not mistake an earlier successful job for a lost regeneration request', async () => {
        useImageStore.setState({
          playerImages: [{ image_id: 1, game_id: 1, image_url: 'old' }] as any,
          portraitImageJob: null,
        });
        (global.fetch as jest.Mock)
          .mockRejectedValueOnce(new TypeError('Failed to fetch'))
          .mockResolvedValueOnce(jsonResponse({
            job_id: 5, game_id: 1, status: 'succeeded', image_id: 1, attempt_count: 1,
          }))
          .mockResolvedValueOnce(jsonResponse({
            images: [{ image_id: 1, game_id: 1, image_url: 'old', entity_key: 'player_main' }], total: 1,
          }));

        await expect(useImageStore.getState().regeneratePlayerImage('short hair'))
          .rejects.toThrow('Failed to fetch');
        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });
    });

    describe('regenerateFreshPlayerImage', () => {
      it('throws error without existing image', async () => {
        await expect(
          useImageStore.getState().regenerateFreshPlayerImage()
        ).rejects.toThrow('没有可重新生成的图片');
      });

      it('queues a fresh candidate batch and preserves the old selection after polling', async () => {
        const old = { image_id: 1, game_id: 1, image_url: 'old', entity_key: 'player_main' };
        const fresh = { image_id: 2, game_id: 1, image_url: 'new', entity_key: 'player_main' };
        const batch = { batch_id: 9, job_id: 11, game_id: 1, mode: 'fresh', status: 'queued', selected_image_id: 1, completed_count: 0, slots: [] };
        useImageStore.getState().setPlayerImage(old as any);
        (global.fetch as jest.Mock).mockImplementation((url: string, options: RequestInit) => Promise.resolve(jsonResponse(
          options?.method === 'POST' ? batch : url.includes('/jobs/latest') ? { job_id: 11, game_id: 1, status: 'succeeded', image_id: null, attempt_count: 1 } : url.includes('/candidates') ? { ...batch, status: 'succeeded', completed_count: 3 } :
          url.includes('/selection') ? { game_id: 1, image_id: 1 } : { images: [old, fresh], total: 2 })));
        await useImageStore.getState().regenerateFreshPlayerImage();
        expect(global.fetch).toHaveBeenCalledWith('/api/images/character/candidates', expect.objectContaining({ method: 'POST' }));
        expect(useImageStore.getState().isGeneratingImage).toBe(true);
        await useImageStore.getState().refreshPortraitImageJob(1);
        expect(useImageStore.getState().playerImages).toEqual([old, fresh]);
        expect(useImageStore.getState().selectedImageId).toBe(1);
        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });

      it('handles regeneration error', async () => {
        const existingImage = { image_id: 1, game_id: 1, image_url: 'old' };
        useImageStore.setState({ playerImages: [existingImage] as any });
        (global.fetch as jest.Mock).mockRejectedValue(new Error('Fresh regeneration failed'));

        await expect(
          useImageStore.getState().regenerateFreshPlayerImage()
        ).rejects.toThrow('Fresh regeneration failed');

        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });
    });

    describe('setImageFeedback', () => {
      it('sets image feedback', () => {
        useImageStore.getState().setImageFeedback('test feedback');
        expect(useImageStore.getState().imageFeedback).toBe('test feedback');
      });
    });
  });

  describe('Opening Illustration Actions', () => {
    describe('setOpeningIllustration', () => {
      it('sets opening illustration', () => {
        const illustration = { image_id: 1, image_url: 'url' };
        useImageStore.getState().setOpeningIllustration(illustration as any);

        expect(useImageStore.getState().openingIllustration).toEqual(illustration);
      });
    });

    describe('setIsGeneratingIllustration', () => {
      it('sets is generating illustration flag', () => {
        useImageStore.getState().setIsGeneratingIllustration(true);
        expect(useImageStore.getState().isGeneratingIllustration).toBe(true);

        useImageStore.getState().setIsGeneratingIllustration(false);
        expect(useImageStore.getState().isGeneratingIllustration).toBe(false);
      });
    });

    describe('setIllustrationError', () => {
      it('sets illustration error', () => {
        useImageStore.getState().setIllustrationError('Test error');
        expect(useImageStore.getState().illustrationError).toBe('Test error');
      });
    });

    describe('generateOpeningIllustration', () => {
      it('returns early without gameId', async () => {
        await useImageStore.getState().generateOpeningIllustration(0, 'story', {}, 'name');
        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('returns early without openingStory', async () => {
        await useImageStore.getState().generateOpeningIllustration(1, '', {}, 'name');
        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('generates opening illustration successfully', async () => {
        const mockResult = { image_id: 1, image_url: 'url' };
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResult));

        await useImageStore.getState().generateOpeningIllustration(1, 'story', {}, 'name');

        expect(useImageStore.getState().openingIllustration).toEqual(mockResult);
        expect(useImageStore.getState().isGeneratingIllustration).toBe(false);
      });

      it('generates opening illustration with player image', async () => {
        const mockResult = { image_id: 1, image_url: 'url' };
        const playerImage = { image_id: 10, image_url: 'player.png' };
        useImageStore.setState({ playerImages: [playerImage] as any });
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResult));

        await useImageStore.getState().generateOpeningIllustration(1, 'story', {}, 'name');

        expect(global.fetch).toHaveBeenCalledWith('/api/images/opening-illustration', expect.objectContaining({ method: 'POST' }));
      });

      it('handles generation error', async () => {
        (global.fetch as jest.Mock).mockRejectedValue(new Error('Failed'));

        await useImageStore.getState().generateOpeningIllustration(1, 'story', {}, 'name');

        expect(useImageStore.getState().illustrationError).toBe('Failed');
        expect(useImageStore.getState().isGeneratingIllustration).toBe(false);
      });
    });

    describe('regenerateOpeningIllustration', () => {
      it('returns early without existing illustration', async () => {
        await useImageStore.getState().regenerateOpeningIllustration(1, 'story', {}, 'name', 'feedback');
        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('returns early without gameId', async () => {
        const existingIllustration = { image_id: 1, image_url: 'old.png' };
        useImageStore.setState({ openingIllustration: existingIllustration as any });
        await useImageStore.getState().regenerateOpeningIllustration(0, 'story', {}, 'name', 'feedback');
        expect(global.fetch).not.toHaveBeenCalled();
      });

      it('regenerates opening illustration successfully', async () => {
        const existingIllustration = { image_id: 1, image_url: 'old.png' };
        const newIllustration = { image_id: 2, image_url: 'new.png' };
        useImageStore.setState({ openingIllustration: existingIllustration as any });
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(newIllustration));

        await useImageStore.getState().regenerateOpeningIllustration(1, 'story', {}, 'name', 'make it brighter');

        expect(global.fetch).toHaveBeenCalledWith('/api/images/opening-illustration/regenerate', expect.objectContaining({ method: 'POST' }));
        expect(useImageStore.getState().openingIllustration).toEqual(newIllustration);
      });

      it('handles regeneration error', async () => {
        const existingIllustration = { image_id: 1, image_url: 'old.png' };
        useImageStore.setState({ openingIllustration: existingIllustration as any });
        (global.fetch as jest.Mock).mockRejectedValue(new Error('Regen failed'));

        try {
          await useImageStore.getState().regenerateOpeningIllustration(1, 'story', {}, 'name', 'feedback');
        } catch (e) {
          // Expected error
        }

        // 验证状态被重置
        expect(useImageStore.getState().isGeneratingIllustration).toBe(false);
      });
    });
  });

  // ★ 场景插画测试已移至 useGameStore.test.ts
});


describe('persistent portrait candidates', () => {
  const images = [11, 22, 33].map(image_id => ({ image_id, game_id: 7, entity_key: 'player_main', image_url: `url${image_id}` }));
  const batch = { batch_id: 9, job_id: 8, game_id: 7, mode: 'initial', status: 'failed', completed_count: 2, selected_image_id: 22,
    slots: [{ slot_index: 0, image_id: 11, status: 'ready' }, { slot_index: 1, image_id: 22, status: 'ready' }, { slot_index: 2, image_id: null, status: 'failed' }] };
  beforeEach(() => { useImageStore.getState().clearCache(); global.fetch = jest.fn(); });
  afterEach(() => { useImageStore.getState().stopPortraitImagePolling(); });
  it('restores server selection for legacy images without a candidate batch', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string) => Promise.resolve(jsonResponse(
      url.includes('/selection') ? { game_id: 7, image_id: 22 } : url.includes('/candidates') ? null : { images })));
    await useImageStore.getState().loadPlayerImages(7);
    expect(useImageStore.getState().selectedImageId).toBe(22);
    expect(useImageStore.getState().playerImage?.image_id).toBe(22);
    expect(useImageStore.getState().portraitCandidates).toBeNull();
  });
  it('restores server selection and preserves it when image order changes', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string) => Promise.resolve(jsonResponse(url.includes('/candidates') ? batch : { images })));
    await useImageStore.getState().loadPlayerImages(7);
    expect(useImageStore.getState().playerImage?.image_id).toBe(22);
    useImageStore.getState().setPlayerImages([...images].reverse() as any);
    expect(useImageStore.getState().playerImage?.image_id).toBe(22);
  });
  it('waits for server selection confirmation and keeps selection after rejection', async () => {
    useImageStore.setState({ playerImages: images as any, playerImage: images[0] as any, selectedImageId: 11 });
    let resolve!: (response: Response) => void;
    (global.fetch as jest.Mock).mockReturnValue(new Promise<Response>(r => { resolve = r; }));
    const pending = useImageStore.getState().selectPlayerImage(22);
    expect(useImageStore.getState().selectedImageId).toBe(11);
    resolve(jsonResponse({ game_id: 7, image_id: 22 })); await pending;
    expect(useImageStore.getState().selectedImageId).toBe(22);
    expect(global.fetch).toHaveBeenCalledWith('/api/images/character/selection', expect.objectContaining({ method: 'PUT', body: JSON.stringify({ game_id: 7, image_id: 22 }) }));
    (global.fetch as jest.Mock).mockRejectedValue(new Error('Rejected'));
    await expect(useImageStore.getState().selectPlayerImage(11)).rejects.toThrow('Rejected');
    expect(useImageStore.getState().selectedImageId).toBe(22);
  });
  it('recovers a lost enqueue response without another generation request', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string, options: RequestInit) => {
      if (options?.method === 'POST') return Promise.reject(new Error('lost response'));
      return Promise.resolve(jsonResponse(url.includes('/candidates') ? { ...batch, status: 'running' } : { images }));
    });
    await useImageStore.getState().enqueuePortraitCandidates(7, 'initial');
    expect(useImageStore.getState().portraitCandidates?.batch_id).toBe(9);
    expect(useImageStore.getState().isGeneratingImage).toBe(true);
    expect((global.fetch as jest.Mock).mock.calls.filter(c => c[1]?.method === 'POST')).toHaveLength(1);
  });
  it('stages a fresh batch while retaining the old selected portrait', async () => {
    useImageStore.setState({ playerImages: images as any, playerImage: images[1] as any, selectedImageId: 22 });
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ ...batch, mode: 'fresh', status: 'queued', completed_count: 0, slots: [0,1,2].map(slot_index => ({ slot_index, status: 'pending', image_id: null })) }));
    await useImageStore.getState().regenerateFreshPlayerImage();
    expect(global.fetch).toHaveBeenCalledWith('/api/images/character/candidates', expect.objectContaining({ body: JSON.stringify({ game_id: 7, mode: 'fresh' }) }));
    expect(useImageStore.getState().playerImage?.image_id).toBe(22);
  });
  it('continues fetching images if a completed batch is ahead of the image list', async () => {
    jest.useFakeTimers();
    const complete = { ...batch, status: 'succeeded', completed_count: 3, slots: [11,22,33].map((image_id, slot_index) => ({ image_id, slot_index, status: 'ready' })) };
    useImageStore.setState({ portraitCandidates: complete });
    let reads = 0;
    (global.fetch as jest.Mock).mockImplementation((url: string) => Promise.resolve(jsonResponse(
      url.includes('/candidates') ? complete : url.includes('/selection') ? { game_id: 7, image_id: 22 } : { images: ++reads === 1 ? images.slice(0, 2) : images })));
    try {
      await useImageStore.getState().refreshPortraitCandidates(7);
      await jest.advanceTimersByTimeAsync(3000);
      expect(useImageStore.getState().playerImages).toHaveLength(3);
      expect(reads).toBe(2);
    } finally { useImageStore.getState().stopPortraitImagePolling(); jest.useRealTimers(); }
  });
  it('retries only the missing slots of the existing batch', async () => {
    useImageStore.setState({ portraitCandidates: batch });
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ ...batch, status: 'queued' }));
    await useImageStore.getState().retryMissingPortraitSlots(9);
    expect(global.fetch).toHaveBeenCalledWith('/api/images/character/candidates/9/retry', expect.objectContaining({ method: 'POST' }));
    expect(useImageStore.getState().portraitCandidates?.completed_count).toBe(2);
  });
});

describe('restoring feedback edits after a page reload', () => {
  const images = [11, 22, 33].map(image_id => ({ image_id, game_id: 7, entity_key: 'player_main', image_url: `url${image_id}` }));
  const completedBatch = { batch_id: 9, job_id: 8, game_id: 7, mode: 'initial', status: 'succeeded', completed_count: 3, selected_image_id: 11,
    slots: images.map((image, slot_index) => ({ slot_index, image_id: image.image_id, status: 'ready' })) };
  beforeEach(() => {
    jest.useFakeTimers();
    useImageStore.getState().clearCache();
    global.fetch = jest.fn();
  });
  afterEach(() => {
    useImageStore.getState().stopPortraitImagePolling();
    jest.useRealTimers();
  });
  it.each(['succeeded', 'failed'] as const)('discovers the running edit and observes terminal %s without enqueueing', async terminal => {
    let finished = false;
    const replacement = { ...images[0], image_id: 44, image_url: 'edited' };
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/jobs/latest')) return Promise.resolve(jsonResponse({ job_id: 10, game_id: 7, attempt_count: 1,
        status: finished ? terminal : 'running', image_id: finished && terminal === 'succeeded' ? 44 : null,
        error_message: finished && terminal === 'failed' ? '编辑失败，原图仍可用' : null }));
      const success = finished && terminal === 'succeeded';
      if (url.includes('/candidates')) return Promise.resolve(jsonResponse(success ? { ...completedBatch, selected_image_id: 44,
        slots: [{ ...completedBatch.slots[0], image_id: 44 }, ...completedBatch.slots.slice(1)] } : completedBatch));
      if (url.includes('/selection')) return Promise.resolve(jsonResponse({ game_id: 7, image_id: success ? 44 : 11 }));
      return Promise.resolve(jsonResponse({ images: success ? [replacement, ...images.slice(1)] : images }));
    });
    await useImageStore.getState().loadPlayerImages(7);
    expect(useImageStore.getState().portraitImageJob).toBeNull();
    await useImageStore.getState().refreshPortraitImageJob(7);
    expect(useImageStore.getState().isGeneratingImage).toBe(true);
    expect(useImageStore.getState().portraitImageJob?.job_id).toBe(10);
    expect(useImageStore.getState().selectedImageId).toBe(11);
    finished = true;
    await jest.advanceTimersByTimeAsync(3000);
    expect(useImageStore.getState().isGeneratingImage).toBe(false);
    expect(useImageStore.getState().selectedImageId).toBe(terminal === 'succeeded' ? 44 : 11);
    expect(useImageStore.getState().imageGenerationError).toBe(terminal === 'failed' ? '编辑失败，原图仍可用' : null);
    const callsAtCompletion = (global.fetch as jest.Mock).mock.calls.length;
    await jest.advanceTimersByTimeAsync(9000);
    expect((global.fetch as jest.Mock).mock.calls).toHaveLength(callsAtCompletion);
    expect((global.fetch as jest.Mock).mock.calls.every(([, options]) => !options?.method)).toBe(true);
  });
  it('keeps a restored running batch recoverable if latest-job discovery disconnects', async () => {
    useImageStore.setState({ portraitCandidates: { ...completedBatch, status: 'running' }, isGeneratingImage: true });
    const warning = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const latest = jest.spyOn(api.images, 'getLatestCharacterPortraitJob')
      .mockRejectedValueOnce(new Error('connection interrupted'))
      .mockResolvedValue({ job_id: 8, game_id: 7, status: 'succeeded', image_id: null, attempt_count: 1 });
    (global.fetch as jest.Mock).mockImplementation((url: string) => Promise.resolve(jsonResponse(
      url.includes('/candidates') ? completedBatch : url.includes('/selection') ? { game_id: 7, image_id: 11 } : { images })));
    try {
      await useImageStore.getState().refreshPortraitImageJob(7);
      await jest.advanceTimersByTimeAsync(3000);
      expect(useImageStore.getState().playerImages).toHaveLength(3);
      expect(useImageStore.getState().isGeneratingImage).toBe(false);
      expect(latest).toHaveBeenCalledTimes(2);
      expect(warning).toHaveBeenCalledWith('[refreshPortraitImageJob] Unable to refresh durable job', expect.any(Error));
    } finally { latest.mockRestore(); warning.mockRestore(); }
  });
  it('recognizes the candidate batch job and stops after completed slots are loaded', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string) => Promise.resolve(jsonResponse(
      url.includes('/jobs/latest') ? { job_id: 8, game_id: 7, status: 'succeeded', image_id: null, attempt_count: 1 } :
      url.includes('/candidates') ? completedBatch : url.includes('/selection') ? { game_id: 7, image_id: 11 } : { images })));
    await useImageStore.getState().loadPlayerImages(7);
    await useImageStore.getState().refreshPortraitImageJob(7);
    expect((global.fetch as jest.Mock).mock.calls.some(([url]) => url.includes('/jobs/latest'))).toBe(true);
    const calls = (global.fetch as jest.Mock).mock.calls.length;
    await jest.advanceTimersByTimeAsync(9000);
    expect((global.fetch as jest.Mock).mock.calls).toHaveLength(calls);
    expect(useImageStore.getState().isGeneratingImage).toBe(false);
  });
});
