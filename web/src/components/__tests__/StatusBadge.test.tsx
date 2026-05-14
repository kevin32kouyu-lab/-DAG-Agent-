import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import StatusBadge, { StatusDot } from '../StatusBadge';

describe('StatusBadge', () => {
  it('renders status label', () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText('✓ 完成')).toBeInTheDocument();
  });

  it('renders custom label when provided', () => {
    render(<StatusBadge status="running" label="Running..." />);
    expect(screen.getByText('Running...')).toBeInTheDocument();
  });

  it('shows pulse indicator when running', () => {
    const { container } = render(<StatusBadge status="running" pulse />);
    const dot = container.querySelector('.animate-pulse');
    expect(dot).toBeInTheDocument();
  });

  it('falls back to raw status text for unknown states', () => {
    render(<StatusBadge status="unknown-state" />);
    expect(screen.getByText('unknown-state')).toBeInTheDocument();
  });
});

describe('StatusDot', () => {
  it.each([
    ['completed', 'bg-green-500'],
    ['running', 'bg-amber-500'],
    ['failed', 'bg-red-500'],
    ['pending', 'bg-gray-600'],
    ['ready', 'bg-blue-500'],
    ['degraded', 'bg-yellow-600'],
  ])('renders %s with %s', (state, expectedClass) => {
    const { container } = render(<StatusDot state={state} />);
    expect(container.firstChild).toHaveClass(expectedClass);
  });
});
