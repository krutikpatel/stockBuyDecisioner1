import type { FundamentalData, ValuationData, EarningsData, NewsSummary, TechnicalIndicators } from '../types/stock';

interface Props {
  technicals: TechnicalIndicators;
  fundamentals: FundamentalData;
  valuation: ValuationData;
  earnings: EarningsData;
  news: NewsSummary;
}

function ScoreRow({ label, score }: { label: string; score: number }) {
  const color = score >= 70 ? 'bg-green-500' : score >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-400 w-28 flex-shrink-0">{label}</span>
      <div className="flex-1 bg-slate-700 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm font-mono text-slate-200 w-10 text-right">{score.toFixed(0)}</span>
    </div>
  );
}

export function ScoreBreakdown({ technicals, fundamentals, valuation, earnings, news }: Props) {
  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <h3 className="text-slate-200 font-semibold mb-4">Score Breakdown</h3>
      <div className="space-y-3">
        <ScoreRow label="Technical" score={technicals.technical_score} />
        <ScoreRow label="Fundamental" score={fundamentals.fundamental_score} />
        <ScoreRow label="Valuation" score={valuation.valuation_score} />
        <ScoreRow label="Earnings" score={earnings.earnings_score} />
        <ScoreRow label="News / Sentiment" score={news.news_score} />
      </div>
    </div>
  );
}
