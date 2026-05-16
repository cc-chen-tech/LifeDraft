/**
 * stores/useImageStore.ts Tests
 * Tests for image state management
 */

import { useImageStore } from '@/stores/useImageStore';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

describe('useImageStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    useImageStore.setState({
      playerImage: null,
      playerImages: [],
      selectedImageIndex: 0,
      isGeneratingImage: false,
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

      it('generates player image successfully', async () => {
        const mockImages = [{ image_id: 1, image_url: 'url1' }];
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ images: mockImages }));

        await useImageStore.getState().generatePlayerImage(1, 'TestPlayer', {
          era: { era: '现代', era_name: '现代' },
          age: { age: 25 },
          gender: { gender: '男' },
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/images/generate', expect.objectContaining({ method: 'POST' }));
        expect(useImageStore.getState().playerImages).toEqual(mockImages);
        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });

      it('handles generation error', async () => {
        (global.fetch as jest.Mock).mockRejectedValue(new Error('API Error'));

        await expect(
          useImageStore.getState().generatePlayerImage(1, 'Test', {})
        ).rejects.toThrow('API Error');

        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });
    });

    describe('regeneratePlayerImage', () => {
      it('throws error without existing image', async () => {
        await expect(
          useImageStore.getState().regeneratePlayerImage('feedback')
        ).rejects.toThrow('没有可重新生成的图片');
      });

      it('regenerates player image successfully', async () => {
        const existingImage = { image_id: 1, image_url: 'old' };
        const newImages = [{ image_id: 2, image_url: 'new' }];
        useImageStore.setState({ playerImages: [existingImage] as any });
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ images: newImages }));

        await useImageStore.getState().regeneratePlayerImage('make it better');

        expect(global.fetch).toHaveBeenCalledWith('/api/images/regenerate', expect.objectContaining({ method: 'POST' }));
        expect(useImageStore.getState().playerImages).toEqual(newImages);
      });

      it('handles regeneration error', async () => {
        const existingImage = { image_id: 1, image_url: 'old' };
        useImageStore.setState({ playerImages: [existingImage] as any });
        (global.fetch as jest.Mock).mockRejectedValue(new Error('Regeneration failed'));

        await expect(
          useImageStore.getState().regeneratePlayerImage('feedback')
        ).rejects.toThrow('Regeneration failed');

        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });
    });

    describe('regenerateFreshPlayerImage', () => {
      it('throws error without existing image', async () => {
        await expect(
          useImageStore.getState().regenerateFreshPlayerImage()
        ).rejects.toThrow('没有可重新生成的图片');
      });

      it('regenerates fresh player image successfully', async () => {
        const existingImage = { image_id: 1, image_url: 'old' };
        const newImages = [{ image_id: 2, image_url: 'new' }];
        useImageStore.setState({ playerImages: [existingImage] as any });
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ images: newImages }));

        await useImageStore.getState().regenerateFreshPlayerImage();

        expect(global.fetch).toHaveBeenCalledWith('/api/images/regenerate-fresh', expect.objectContaining({ method: 'POST' }));
        expect(useImageStore.getState().playerImages).toEqual(newImages);
      });

      it('handles regeneration error', async () => {
        const existingImage = { image_id: 1, image_url: 'old' };
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

        expect(global.fetch).toHaveBeenCalledWith('/api/images/opening', expect.objectContaining({ method: 'POST' }));
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

        expect(global.fetch).toHaveBeenCalledWith('/api/images/opening/regenerate', expect.objectContaining({ method: 'POST' }));
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
