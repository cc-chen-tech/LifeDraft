/**
 * stores/useImageStore.ts Tests
 * Tests for image state management
 */

import { useImageStore } from '@/stores/useImageStore';
import api from '@/lib/api';

// Mock API
jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    images: {
      generate: jest.fn(),
      regenerate: jest.fn(),
      regenerateFresh: jest.fn(),
      generateOpeningIllustration: jest.fn(),
      regenerateOpeningIllustration: jest.fn(),
      // ★ 场景插画 API 已移至 useGameStore
    },
  },
}));

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
        (api.images.generate as jest.Mock).mockResolvedValue({ images: mockImages });

        await useImageStore.getState().generatePlayerImage(1, 'TestPlayer', {
          era: { era_name: '现代' },
          age: { age: 25 },
          gender: { gender: '男' },
        });

        expect(api.images.generate).toHaveBeenCalled();
        expect(useImageStore.getState().playerImages).toEqual(mockImages);
        expect(useImageStore.getState().isGeneratingImage).toBe(false);
      });

      it('handles generation error', async () => {
        (api.images.generate as jest.Mock).mockRejectedValue(new Error('API Error'));

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
        (api.images.regenerate as jest.Mock).mockResolvedValue({ images: newImages });

        await useImageStore.getState().regeneratePlayerImage('make it better');

        expect(api.images.regenerate).toHaveBeenCalledWith({
          image_id: 1,
          feedback: 'make it better',
        });
        expect(useImageStore.getState().playerImages).toEqual(newImages);
      });

      it('handles regeneration error', async () => {
        const existingImage = { image_id: 1, image_url: 'old' };
        useImageStore.setState({ playerImages: [existingImage] as any });
        (api.images.regenerate as jest.Mock).mockRejectedValue(new Error('Regeneration failed'));

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
        (api.images.regenerateFresh as jest.Mock).mockResolvedValue({ images: newImages });

        await useImageStore.getState().regenerateFreshPlayerImage();

        expect(api.images.regenerateFresh).toHaveBeenCalledWith(1, true);
        expect(useImageStore.getState().playerImages).toEqual(newImages);
      });

      it('handles regeneration error', async () => {
        const existingImage = { image_id: 1, image_url: 'old' };
        useImageStore.setState({ playerImages: [existingImage] as any });
        (api.images.regenerateFresh as jest.Mock).mockRejectedValue(new Error('Fresh regeneration failed'));

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
        expect(api.images.generateOpeningIllustration).not.toHaveBeenCalled();
      });

      it('returns early without openingStory', async () => {
        await useImageStore.getState().generateOpeningIllustration(1, '', {}, 'name');
        expect(api.images.generateOpeningIllustration).not.toHaveBeenCalled();
      });

      it('generates opening illustration successfully', async () => {
        const mockResult = { image_id: 1, image_url: 'url' };
        (api.images.generateOpeningIllustration as jest.Mock).mockResolvedValue(mockResult);

        await useImageStore.getState().generateOpeningIllustration(1, 'story', {}, 'name');

        expect(useImageStore.getState().openingIllustration).toEqual(mockResult);
        expect(useImageStore.getState().isGeneratingIllustration).toBe(false);
      });

      it('generates opening illustration with player image', async () => {
        const mockResult = { image_id: 1, image_url: 'url' };
        const playerImage = { image_id: 10, image_url: 'player.png' };
        useImageStore.setState({ playerImages: [playerImage] as any });
        (api.images.generateOpeningIllustration as jest.Mock).mockResolvedValue(mockResult);

        await useImageStore.getState().generateOpeningIllustration(1, 'story', {}, 'name');

        expect(api.images.generateOpeningIllustration).toHaveBeenCalledWith(
          expect.objectContaining({ player_image_id: 10 })
        );
      });

      it('handles generation error', async () => {
        (api.images.generateOpeningIllustration as jest.Mock).mockRejectedValue(new Error('Failed'));

        await useImageStore.getState().generateOpeningIllustration(1, 'story', {}, 'name');

        expect(useImageStore.getState().illustrationError).toBe('Failed');
        expect(useImageStore.getState().isGeneratingIllustration).toBe(false);
      });
    });

    describe('regenerateOpeningIllustration', () => {
      it('returns early without existing illustration', async () => {
        await useImageStore.getState().regenerateOpeningIllustration(1, 'story', {}, 'name', 'feedback');
        expect(api.images.regenerateOpeningIllustration).not.toHaveBeenCalled();
      });

      it('returns early without gameId', async () => {
        const existingIllustration = { image_id: 1, image_url: 'old.png' };
        useImageStore.setState({ openingIllustration: existingIllustration as any });
        await useImageStore.getState().regenerateOpeningIllustration(0, 'story', {}, 'name', 'feedback');
        expect(api.images.regenerateOpeningIllustration).not.toHaveBeenCalled();
      });

      it('regenerates opening illustration successfully', async () => {
        const existingIllustration = { image_id: 1, image_url: 'old.png' };
        const newIllustration = { image_id: 2, image_url: 'new.png' };
        useImageStore.setState({ openingIllustration: existingIllustration as any });
        (api.images.regenerateOpeningIllustration as jest.Mock).mockResolvedValue(newIllustration);

        await useImageStore.getState().regenerateOpeningIllustration(1, 'story', {}, 'name', 'make it brighter');

        expect(api.images.regenerateOpeningIllustration).toHaveBeenCalledWith(
          expect.objectContaining({ current_illustration_id: 1 })
        );
        expect(useImageStore.getState().openingIllustration).toEqual(newIllustration);
      });

      it('handles regeneration error', async () => {
        const existingIllustration = { image_id: 1, image_url: 'old.png' };
        useImageStore.setState({ openingIllustration: existingIllustration as any });
        (api.images.regenerateOpeningIllustration as jest.Mock).mockRejectedValue(new Error('Regen failed'));

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
