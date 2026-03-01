/**
 * stores/useUIStore.ts Tests
 * Tests for UI state management
 */
import { act } from '@testing-library/react';
import { useUIStore } from '@/stores/useUIStore';

describe('useUIStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    act(() => {
      useUIStore.setState({
        activeModal: null,
        modalData: {},
        isProcessing: false,
        processingMessage: '',
        isStreaming: false,
        language: 'zh',
        sidebarOpen: false,
      });
    });
  });

  describe('Initial state', () => {
    it('has correct initial values', () => {
      const state = useUIStore.getState();

      expect(state.activeModal).toBeNull();
      expect(state.modalData).toEqual({});
      expect(state.isProcessing).toBe(false);
      expect(state.processingMessage).toBe('');
      expect(state.isStreaming).toBe(false);
      expect(state.language).toBe('zh');
      expect(state.sidebarOpen).toBe(false);
    });
  });

  describe('Modal management', () => {
    it('opens a modal without data', () => {
      act(() => {
        useUIStore.getState().openModal('login');
      });

      const state = useUIStore.getState();
      expect(state.activeModal).toBe('login');
      expect(state.modalData).toEqual({});
    });

    it('opens a modal with data', () => {
      act(() => {
        useUIStore.getState().openModal('confirm-delete', { itemId: 123 });
      });

      const state = useUIStore.getState();
      expect(state.activeModal).toBe('confirm-delete');
      expect(state.modalData).toEqual({ itemId: 123 });
    });

    it('closes the modal', () => {
      act(() => {
        useUIStore.getState().openModal('login', { redirect: '/play' });
        useUIStore.getState().closeModal();
      });

      const state = useUIStore.getState();
      expect(state.activeModal).toBeNull();
      expect(state.modalData).toEqual({});
    });

    it('handles all modal types', () => {
      const modalTypes = [
        'login',
        'register',
        'save-preset',
        'load-preset',
        'confirm-delete',
        'story-adjuster',
        'game-menu',
      ] as const;

      for (const modalType of modalTypes) {
        act(() => {
          useUIStore.getState().openModal(modalType);
        });

        expect(useUIStore.getState().activeModal).toBe(modalType);
      }
    });
  });

  describe('Processing states', () => {
    it('sets processing state with message', () => {
      act(() => {
        useUIStore.getState().setProcessing(true, 'Loading...');
      });

      const state = useUIStore.getState();
      expect(state.isProcessing).toBe(true);
      expect(state.processingMessage).toBe('Loading...');
    });

    it('sets processing state without message', () => {
      act(() => {
        useUIStore.getState().setProcessing(true);
      });

      const state = useUIStore.getState();
      expect(state.isProcessing).toBe(true);
      expect(state.processingMessage).toBe('');
    });

    it('clears processing state', () => {
      act(() => {
        useUIStore.getState().setProcessing(true, 'Loading...');
        useUIStore.getState().setProcessing(false);
      });

      const state = useUIStore.getState();
      expect(state.isProcessing).toBe(false);
      expect(state.processingMessage).toBe('');
    });

    it('sets streaming state', () => {
      act(() => {
        useUIStore.getState().setStreaming(true);
      });

      expect(useUIStore.getState().isStreaming).toBe(true);
    });

    it('clears streaming state', () => {
      act(() => {
        useUIStore.getState().setStreaming(true);
        useUIStore.getState().setStreaming(false);
      });

      expect(useUIStore.getState().isStreaming).toBe(false);
    });
  });

  describe('Language', () => {
    it('sets language to Chinese', () => {
      act(() => {
        useUIStore.getState().setLanguage('zh');
      });

      expect(useUIStore.getState().language).toBe('zh');
    });

    it('sets language to English', () => {
      act(() => {
        useUIStore.getState().setLanguage('en');
      });

      expect(useUIStore.getState().language).toBe('en');
    });

    it('can switch languages', () => {
      act(() => {
        useUIStore.getState().setLanguage('en');
        useUIStore.getState().setLanguage('zh');
      });

      expect(useUIStore.getState().language).toBe('zh');
    });
  });

  describe('Sidebar', () => {
    it('toggles sidebar open', () => {
      act(() => {
        useUIStore.getState().toggleSidebar();
      });

      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });

    it('toggles sidebar closed', () => {
      act(() => {
        useUIStore.getState().toggleSidebar();
        useUIStore.getState().toggleSidebar();
      });

      expect(useUIStore.getState().sidebarOpen).toBe(false);
    });

    it('can toggle multiple times', () => {
      act(() => {
        useUIStore.getState().toggleSidebar(); // true
        useUIStore.getState().toggleSidebar(); // false
        useUIStore.getState().toggleSidebar(); // true
      });

      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });
  });

  describe('State updates', () => {
    it('updates are independent', () => {
      act(() => {
        useUIStore.getState().openModal('login');
        useUIStore.getState().setProcessing(true, 'Processing');
        useUIStore.getState().setStreaming(true);
        useUIStore.getState().setLanguage('en');
        useUIStore.getState().toggleSidebar();
      });

      const state = useUIStore.getState();
      expect(state.activeModal).toBe('login');
      expect(state.isProcessing).toBe(true);
      expect(state.processingMessage).toBe('Processing');
      expect(state.isStreaming).toBe(true);
      expect(state.language).toBe('en');
      expect(state.sidebarOpen).toBe(true);
    });

    it('can open different modals in sequence', () => {
      act(() => {
        useUIStore.getState().openModal('login');
      });
      expect(useUIStore.getState().activeModal).toBe('login');

      act(() => {
        useUIStore.getState().openModal('register');
      });
      expect(useUIStore.getState().activeModal).toBe('register');

      act(() => {
        useUIStore.getState().openModal('game-menu');
      });
      expect(useUIStore.getState().activeModal).toBe('game-menu');
    });
  });
});
