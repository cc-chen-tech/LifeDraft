/**
 * OptionCards Component Tests
 * Tests all interactive elements of the option cards component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OptionCards } from '@/components/game/OptionCards';

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

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
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
