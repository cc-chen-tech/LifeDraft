/**
 * OptionCards Component Tests
 * Tests all interactive elements of the option cards component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OptionCards } from '@/components/game/OptionCards';
import { INPUT_LIMITS } from '@/types/input-limits.generated';

describe('OptionCards', () => {
  const mockOptions = [
    { text: 'Option 1', potential_effects: { mood: 10 } },
    { text: 'Option 2', potential_effects: { energy: -5 } },
    { text: 'Option 3', potential_effects: { knowledge: 5 } },
  ];

  const mockOnSelect = jest.fn();
  const mockOnCustomChoice = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('shows the generated limit without a UTF-16 native maxlength', () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );
      expect(screen.getByPlaceholderText(/或者，描述你想做的事情/i)).not.toHaveAttribute('maxlength');
      expect(screen.getByText(`还可输入 ${INPUT_LIMITS.customAction} 字`)).toBeInTheDocument();
    });
    it('renders all options', () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      expect(screen.getByText('Option 1')).toBeInTheDocument();
      expect(screen.getByText('Option 2')).toBeInTheDocument();
      expect(screen.getByText('Option 3')).toBeInTheDocument();
    });

    it('renders option numbers', () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      expect(screen.getByTestId('option-ordinal-0')).toHaveTextContent('1');
      expect(screen.getByTestId('option-ordinal-1')).toHaveTextContent('2');
      expect(screen.getByTestId('option-ordinal-2')).toHaveTextContent('3');
      expect(screen.queryByText('01')).not.toBeInTheDocument();
    });

    it('renders custom input section', () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      expect(
        screen.getByPlaceholderText(/或者，描述你想做的事情/i)
      ).toBeInTheDocument();
    });

    it('renders section hint', () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      expect(screen.getByText('你的选择')).toBeInTheDocument();
    });

    it('renders generated choices as flat branch rows without card or glow decoration', () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const branches = screen.getAllByRole('button', { name: /选择 \d：/ });
      expect(branches).toHaveLength(3);

      for (const branch of branches) {
        expect(branch).toHaveAttribute('data-slot', 'choice-branch-row');
        expect(branch).toHaveClass(
          'rounded-none',
          'border-x-0',
          'border-t-0',
          'bg-transparent',
          'shadow-none',
        );
        expect(branch).not.toHaveClass('option-card', 'rounded-lg', 'bg-card/50');
      }

      const firstOrdinal = screen.getByTestId('option-ordinal-0');
      expect(firstOrdinal).toHaveTextContent('1');
      expect(firstOrdinal).toHaveClass('text-xs');
      expect(firstOrdinal).not.toHaveClass('text-[11px]');
      expect(firstOrdinal).not.toHaveClass('rounded', 'bg-primary/10');
    });

    it('uses a labelled FormField with one described underline touch textarea', () => {
      const { container } = render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByRole('textbox', { name: '写下自己的选择' });
      expect(textarea.tagName).toBe('TEXTAREA');
      expect(textarea).toHaveAttribute('data-surface', 'underline');
      expect(textarea).toHaveAttribute('data-control-size', 'touch');

      const field = textarea.closest('[data-slot="form-field"]');
      expect(field).not.toBeNull();
      const describedBy = textarea.getAttribute('aria-describedby')?.split(/\s+/) ?? [];
      expect(describedBy).toHaveLength(2);
      expect(describedBy.map((id) => document.getElementById(id)?.textContent)).toEqual([
        '回车提交，Shift + Enter 换行',
        `还可输入 ${INPUT_LIMITS.customAction} 字`,
      ]);
      expect(field?.querySelectorAll('[aria-live]')).toHaveLength(0);
      expect(container.querySelectorAll('[data-slot="form-field"]')).toHaveLength(1);
    });
  });

  describe('Option selection', () => {
    it('calls onSelect when clicking an option', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      await user.click(screen.getByText('Option 1'));

      expect(mockOnSelect).toHaveBeenCalledWith(0);
    });

    it('calls onSelect with correct index for second option', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      await user.click(screen.getByText('Option 2'));

      expect(mockOnSelect).toHaveBeenCalledWith(1);
    });

    it('calls onSelect with correct index for third option', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      await user.click(screen.getByText('Option 3'));

      expect(mockOnSelect).toHaveBeenCalledWith(2);
    });

    it('immediately disables every choice and shows selected loading feedback', async () => {
      const user = userEvent.setup();
      let finishSelection: (() => void) | undefined;
      mockOnSelect.mockImplementationOnce(
        () => new Promise<void>((resolve) => { finishSelection = resolve; })
      );
      const { container } = render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      await user.click(screen.getByRole('button', { name: '选择 2：Option 2' }));

      expect(screen.getByText('正在进入')).toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveClass('text-sm');
      expect(container.querySelectorAll('[aria-live], [role="status"]')).toHaveLength(1);
      for (const button of screen.getAllByRole('button', { name: /选择 \d：/ })) {
        expect(button).toBeDisabled();
      }
      expect(screen.getByPlaceholderText(/或者，描述你想做的事情/i)).toBeDisabled();

      finishSelection?.();
      await waitFor(() => {
        expect(screen.getByRole('button', { name: '选择 1：Option 1' })).toBeEnabled();
      });
    });

    it('unlocks choices after a synchronous selection callback completes', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const first = screen.getByRole('button', { name: '选择 1：Option 1' });
      await user.click(first);

      await waitFor(() => expect(first).toBeEnabled());
      await user.click(first);
      expect(mockOnSelect).toHaveBeenCalledTimes(2);
    });

    it('keeps long branch copy fully visible instead of clamping it', () => {
      const fullText = '这是一个需要完整显示给所有读者、允许自然换行而不能在两行后截断的很长故事选项文本';
      render(
        <OptionCards
          options={[{ text: fullText }]}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const button = screen.getByRole('button', { name: `选择 1：${fullText}` });
      expect(button).toHaveAttribute('title', fullText);
      expect(button).toHaveClass('min-h-14');
      expect(screen.getByTestId('option-text-0')).toHaveClass('whitespace-normal', 'break-words');
      expect(screen.getByTestId('option-text-0')).not.toHaveClass('line-clamp-2', 'truncate');
    });

    it('does not call onSelect when disabled', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
          disabled
        />
      );

      await user.click(screen.getByText('Option 1'));

      expect(mockOnSelect).not.toHaveBeenCalled();
    });
  });

  describe('Custom choice input', () => {
    it('keeps an injected overlimit value visible and blocks submission', async () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );
      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      fireEvent.change(textarea, {
        target: { value: '😀'.repeat(INPUT_LIMITS.customAction + 1) },
      });
      expect(screen.getByRole('alert')).toHaveTextContent('已超出 1 字');
      expect(screen.getByRole('button', { name: '提交自定义选择' })).toBeDisabled();
      expect(mockOnCustomChoice).not.toHaveBeenCalled();
    });

    it('allows typing in custom input', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      await user.type(textarea, 'My custom action');

      expect(textarea).toHaveValue('My custom action');
    });

    it('calls onCustomChoice when clicking send button', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      await user.type(textarea, 'My custom action');

      // Find the send button (it's a button with Send icon)
      const sendButtons = screen.getAllByRole('button');
      const sendButton = sendButtons[sendButtons.length - 1]; // Last button is send
      await user.click(sendButton);

      expect(mockOnCustomChoice).toHaveBeenCalledWith('My custom action');
    });

    it('calls onCustomChoice on Enter key (without shift)', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      await user.type(textarea, 'My custom action');
      
      // Press Enter without shift
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      expect(mockOnCustomChoice).toHaveBeenCalledWith('My custom action');
    });

    it('does not call onCustomChoice on Shift+Enter', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      await user.type(textarea, 'My custom action');
      
      // Press Shift+Enter
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });

      expect(mockOnCustomChoice).not.toHaveBeenCalled();
    });

    it('clears input after submitting custom choice', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      await user.type(textarea, 'My custom action');
      
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      expect(textarea).toHaveValue('');
    });

    it('does not call onCustomChoice with empty input', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      expect(mockOnCustomChoice).not.toHaveBeenCalled();
    });

    it('does not call onCustomChoice with whitespace-only input', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      await user.type(textarea, '   ');
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      expect(mockOnCustomChoice).not.toHaveBeenCalled();
    });

    it('trims whitespace from custom choice', async () => {
      const user = userEvent.setup();
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      await user.type(textarea, '  My custom action  ');
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      expect(mockOnCustomChoice).toHaveBeenCalledWith('My custom action');
    });

    it('disables custom input when disabled prop is true', async () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
          disabled
        />
      );

      const textarea = screen.getByPlaceholderText(/或者，描述你想做的事情/i);
      expect(textarea).toBeDisabled();
    });
  });

  describe('Disabled state', () => {
    it('shows options with disabled styling', () => {
      render(
        <OptionCards
          options={mockOptions}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
          disabled
        />
      );

      // Options should still be visible but disabled
      expect(screen.getByText('Option 1')).toBeInTheDocument();
      expect(screen.getByText('Option 2')).toBeInTheDocument();
      expect(screen.getByText('Option 3')).toBeInTheDocument();
    });
  });

  describe('Empty options', () => {
    it('renders empty state when no options', () => {
      render(
        <OptionCards
          options={[]}
          onSelect={mockOnSelect}
          onCustomChoice={mockOnCustomChoice}
        />
      );

      // Should still show custom input
      expect(
        screen.getByPlaceholderText(/或者，描述你想做的事情/i)
      ).toBeInTheDocument();
    });
  });
});
