/**
 * Tests for Card UI components
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardAction,
  CardContent,
  CardFooter,
} from '@/components/ui/card';

describe('Card Components', () => {
  describe('Card', () => {
    it('renders with default props', () => {
      render(<Card data-testid="card">Card Content</Card>);
      expect(screen.getByTestId('card')).toBeInTheDocument();
      expect(screen.getByText('Card Content')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<Card className="custom-class" data-testid="card">Content</Card>);
      const card = screen.getByTestId('card');
      expect(card).toHaveClass('custom-class');
    });
  });

  describe('CardHeader', () => {
    it('renders with default props', () => {
      render(<CardHeader data-testid="header">Header Content</CardHeader>);
      expect(screen.getByTestId('header')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<CardHeader className="custom-header" data-testid="header">Header</CardHeader>);
      const header = screen.getByTestId('header');
      expect(header).toHaveClass('custom-header');
    });
  });

  describe('CardTitle', () => {
    it('renders title text', () => {
      render(<CardTitle data-testid="title">Card Title</CardTitle>);
      expect(screen.getByText('Card Title')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<CardTitle className="custom-title" data-testid="title">Title</CardTitle>);
      const title = screen.getByTestId('title');
      expect(title).toHaveClass('custom-title');
    });
  });

  describe('CardDescription', () => {
    it('renders description text', () => {
      render(<CardDescription data-testid="desc">Card Description</CardDescription>);
      expect(screen.getByText('Card Description')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<CardDescription className="custom-desc" data-testid="desc">Desc</CardDescription>);
      const desc = screen.getByTestId('desc');
      expect(desc).toHaveClass('custom-desc');
    });
  });

  describe('CardAction', () => {
    it('renders action content', () => {
      render(<CardAction data-testid="action">Action Button</CardAction>);
      expect(screen.getByText('Action Button')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<CardAction className="custom-action" data-testid="action">Action</CardAction>);
      const action = screen.getByTestId('action');
      expect(action).toHaveClass('custom-action');
    });
  });

  describe('CardContent', () => {
    it('renders content', () => {
      render(<CardContent data-testid="content">Main Content</CardContent>);
      expect(screen.getByText('Main Content')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<CardContent className="custom-content" data-testid="content">Content</CardContent>);
      const content = screen.getByTestId('content');
      expect(content).toHaveClass('custom-content');
    });
  });

  describe('CardFooter', () => {
    it('renders footer content', () => {
      render(<CardFooter data-testid="footer">Footer Content</CardFooter>);
      expect(screen.getByText('Footer Content')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<CardFooter className="custom-footer" data-testid="footer">Footer</CardFooter>);
      const footer = screen.getByTestId('footer');
      expect(footer).toHaveClass('custom-footer');
    });
  });

  describe('Combined Card', () => {
    it('renders a complete card with all components', () => {
      render(
        <Card data-testid="full-card">
          <CardHeader>
            <CardTitle>Test Title</CardTitle>
            <CardDescription>Test Description</CardDescription>
            <CardAction>Test Action</CardAction>
          </CardHeader>
          <CardContent>Test Content</CardContent>
          <CardFooter>Test Footer</CardFooter>
        </Card>
      );

      expect(screen.getByText('Test Title')).toBeInTheDocument();
      expect(screen.getByText('Test Description')).toBeInTheDocument();
      expect(screen.getByText('Test Action')).toBeInTheDocument();
      expect(screen.getByText('Test Content')).toBeInTheDocument();
      expect(screen.getByText('Test Footer')).toBeInTheDocument();
    });
  });
});
