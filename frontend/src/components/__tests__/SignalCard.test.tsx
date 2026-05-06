import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SignalCard } from '../SignalCard';
import type { SignalCard as SignalCardType } from '../../types/stock';

function makeCard(overrides: Partial<SignalCardType> = {}): SignalCardType {
  return {
    name: 'momentum',
    score: 75,
    label: 'BULLISH',
    explanation: 'Strong upward price momentum detected.',
    top_positives: ['RSI rising', 'Price above SMA50'],
    top_negatives: [],
    missing_data_warnings: [],
    ...overrides,
  };
}

describe('SignalCard', () => {
  it('renders card name', () => {
    render(<SignalCard card={makeCard()} />);
    expect(screen.getByText('momentum')).toBeInTheDocument();
  });

  it('renders score value', () => {
    render(<SignalCard card={makeCard({ score: 82.4 })} />);
    expect(screen.getByText('82')).toBeInTheDocument();
  });

  it('renders label badge', () => {
    render(<SignalCard card={makeCard({ label: 'VERY_BULLISH', score: 90 })} />);
    expect(screen.getByText('VERY BULLISH')).toBeInTheDocument();
  });

  it('renders BEARISH label with underscore replaced', () => {
    render(<SignalCard card={makeCard({ label: 'VERY_BEARISH', score: 10 })} />);
    expect(screen.getByText('VERY BEARISH')).toBeInTheDocument();
  });

  it('renders explanation text', () => {
    render(<SignalCard card={makeCard({ explanation: 'Momentum is weakening.' })} />);
    expect(screen.getByText('Momentum is weakening.')).toBeInTheDocument();
  });

  it('does not show expand button when no factors', () => {
    const card = makeCard({ top_positives: [], top_negatives: [], missing_data_warnings: [] });
    render(<SignalCard card={card} />);
    expect(screen.queryByText(/Show factors/)).not.toBeInTheDocument();
  });

  it('shows expand button when positives exist', () => {
    render(<SignalCard card={makeCard()} />);
    expect(screen.getByText(/Show factors/)).toBeInTheDocument();
  });

  it('expands to show positives on click', () => {
    render(<SignalCard card={makeCard()} />);
    fireEvent.click(screen.getByText(/Show factors/));
    expect(screen.getByText('Positives')).toBeInTheDocument();
    expect(screen.getByText('✓ RSI rising')).toBeInTheDocument();
    expect(screen.getByText('✓ Price above SMA50')).toBeInTheDocument();
  });

  it('collapses factors on second click', () => {
    render(<SignalCard card={makeCard()} />);
    fireEvent.click(screen.getByText(/Show factors/));
    expect(screen.getByText('Positives')).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Hide factors/));
    expect(screen.queryByText('Positives')).not.toBeInTheDocument();
  });

  it('shows negatives when expanded', () => {
    const card = makeCard({ top_negatives: ['Volume declining'], top_positives: [] });
    render(<SignalCard card={card} />);
    fireEvent.click(screen.getByText(/Show factors/));
    expect(screen.getByText('Negatives')).toBeInTheDocument();
    expect(screen.getByText('✗ Volume declining')).toBeInTheDocument();
  });

  it('shows missing data warnings when expanded', () => {
    const card = makeCard({
      missing_data_warnings: ['No earnings data'],
      top_positives: [],
      top_negatives: [],
    });
    render(<SignalCard card={card} />);
    fireEvent.click(screen.getByText(/Show factors/));
    expect(screen.getByText('Missing Data')).toBeInTheDocument();
    expect(screen.getByText('⚠ No earnings data')).toBeInTheDocument();
  });

  it('renders score gauge bar with correct width', () => {
    const { container } = render(<SignalCard card={makeCard({ score: 60 })} />);
    const bar = container.querySelector('[style*="width: 60%"]');
    expect(bar).not.toBeNull();
  });

  it('renders NEUTRAL label', () => {
    render(<SignalCard card={makeCard({ label: 'NEUTRAL', score: 50 })} />);
    expect(screen.getByText('NEUTRAL')).toBeInTheDocument();
  });

  it('renders name with underscore replaced by space', () => {
    render(<SignalCard card={makeCard({ name: 'entry_timing' })} />);
    expect(screen.getByText('entry timing')).toBeInTheDocument();
  });
});
