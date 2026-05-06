import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PerformanceTable } from '../PerformanceTable';
import { OwnershipPanel } from '../OwnershipPanel';
import { VolumePanel } from '../VolumePanel';
import type { TechnicalIndicators, FundamentalData } from '../../types/stock';

// Minimal TechnicalIndicators for PerformanceTable
function makeTechnicals(overrides: Partial<TechnicalIndicators> = {}): TechnicalIndicators {
  return {
    volume_trend: 'average',
    trend: { label: 'sideways', description: 'Sideways' },
    is_extended: false,
    support_resistance: { supports: [], resistances: [] },
    technical_score: 50,
    obv_trend: 0,
    ad_trend: 0,
    gap_filled: false,
    ...overrides,
  };
}

// Minimal FundamentalData for OwnershipPanel
function makeFundamentals(overrides: Partial<FundamentalData> = {}): FundamentalData {
  return {
    fundamental_score: 60,
    archetype: 'PROFITABLE_GROWTH',
    archetype_confidence: 0.7,
    ...overrides,
  };
}

// ----------------------------------------------------------------
// PerformanceTable tests
// ----------------------------------------------------------------
describe('PerformanceTable', () => {
  it('renders all period labels', () => {
    render(<PerformanceTable technicals={makeTechnicals()} />);
    expect(screen.getByText('1W')).toBeInTheDocument();
    expect(screen.getByText('1M')).toBeInTheDocument();
    expect(screen.getByText('3M')).toBeInTheDocument();
    expect(screen.getByText('6M')).toBeInTheDocument();
    expect(screen.getByText('YTD')).toBeInTheDocument();
    expect(screen.getByText('1Y')).toBeInTheDocument();
    expect(screen.getByText('3Y')).toBeInTheDocument();
    expect(screen.getByText('5Y')).toBeInTheDocument();
  });

  it('shows N/A when performance data is missing', () => {
    render(<PerformanceTable technicals={makeTechnicals()} />);
    const nas = screen.getAllByText('N/A');
    expect(nas.length).toBeGreaterThanOrEqual(8);
  });

  it('shows positive return in green', () => {
    const { container } = render(
      <PerformanceTable technicals={makeTechnicals({ perf_1w: 3.5 })} />
    );
    expect(screen.getByText('+3.50%')).toBeInTheDocument();
    const el = screen.getByText('+3.50%');
    expect(el.className).toMatch(/green/);
  });

  it('shows negative return in red', () => {
    render(<PerformanceTable technicals={makeTechnicals({ perf_1m: -2.1 })} />);
    expect(screen.getByText('-2.10%')).toBeInTheDocument();
    const el = screen.getByText('-2.10%');
    expect(el.className).toMatch(/red/);
  });

  it('shows max drawdown when present', () => {
    render(<PerformanceTable technicals={makeTechnicals({ max_drawdown_3m: -8.5, max_drawdown_1y: -22.3 })} />);
    expect(screen.getByText('-8.50%')).toBeInTheDocument();
    expect(screen.getByText('-22.30%')).toBeInTheDocument();
  });

  it('does not crash with all null performance values', () => {
    expect(() => render(<PerformanceTable technicals={makeTechnicals()} />)).not.toThrow();
  });
});

// ----------------------------------------------------------------
// OwnershipPanel tests
// ----------------------------------------------------------------
describe('OwnershipPanel', () => {
  it('renders panel heading', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals()} />);
    expect(screen.getByText('Ownership')).toBeInTheDocument();
  });

  it('shows insider ownership when present', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals({ insider_ownership: 5.2 })} />);
    expect(screen.getByText('5.20%')).toBeInTheDocument();
  });

  it('shows N/A for insider ownership when absent', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals()} />);
    // Should have multiple N/As for missing fields
    const nas = screen.getAllByText('N/A');
    expect(nas.length).toBeGreaterThanOrEqual(4);
  });

  it('shows institutional ownership when present', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals({ institutional_ownership: 72.5 })} />);
    expect(screen.getByText('72.50%')).toBeInTheDocument();
  });

  it('shows short float when present', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals({ short_float: 3.8 })} />);
    expect(screen.getByText('3.80%')).toBeInTheDocument();
  });

  it('shows analyst target distance when present', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals({ target_price_distance: 18.5 })} />);
    expect(screen.getByText('18.50%')).toBeInTheDocument();
  });

  it('shows insider transactions direction when present', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals({ insider_transactions: 150000 })} />);
    // Positive transactions = buying
    expect(screen.getByText(/Buying/i)).toBeInTheDocument();
  });

  it('shows insider selling when transactions negative', () => {
    render(<OwnershipPanel fundamentals={makeFundamentals({ insider_transactions: -50000 })} />);
    expect(screen.getByText(/Selling/i)).toBeInTheDocument();
  });
});

// ----------------------------------------------------------------
// VolumePanel tests
// ----------------------------------------------------------------
describe('VolumePanel', () => {
  it('renders panel heading', () => {
    render(<VolumePanel technicals={makeTechnicals()} />);
    expect(screen.getByText('Volume & Accumulation')).toBeInTheDocument();
  });

  it('shows OBV rising when obv_trend is 1', () => {
    render(<VolumePanel technicals={makeTechnicals({ obv_trend: 1 })} />);
    expect(screen.getByText('Rising')).toBeInTheDocument();
  });

  it('shows OBV falling when obv_trend is -1', () => {
    render(<VolumePanel technicals={makeTechnicals({ obv_trend: -1 })} />);
    expect(screen.getByText('Falling')).toBeInTheDocument();
  });

  it('shows CMF value when present', () => {
    render(<VolumePanel technicals={makeTechnicals({ chaikin_money_flow: 0.15 })} />);
    expect(screen.getByText('0.15')).toBeInTheDocument();
  });

  it('shows N/A for CMF when absent', () => {
    render(<VolumePanel technicals={makeTechnicals()} />);
    const nas = screen.getAllByText('N/A');
    expect(nas.length).toBeGreaterThanOrEqual(1);
  });

  it('shows VWAP deviation when present', () => {
    render(<VolumePanel technicals={makeTechnicals({ vwap_deviation: 2.3 })} />);
    expect(screen.getByText('+2.30%')).toBeInTheDocument();
  });

  it('shows up/down volume ratio when present', () => {
    render(<VolumePanel technicals={makeTechnicals({ updown_volume_ratio: 1.5 })} />);
    expect(screen.getByText('1.50')).toBeInTheDocument();
  });

  it('does not crash with all default values', () => {
    expect(() => render(<VolumePanel technicals={makeTechnicals()} />)).not.toThrow();
  });
});
