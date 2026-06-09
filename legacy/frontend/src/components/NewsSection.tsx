import type { NewsSummary, NewsItem } from '../types/stock';

const SENTIMENT_BADGE: Record<string, string> = {
  positive: 'bg-green-900/60 text-green-300 border-green-700',
  negative: 'bg-red-900/60 text-red-300 border-red-700',
  neutral:  'bg-slate-700/60 text-slate-300 border-slate-600',
};

const IMPORTANCE_DOT: Record<string, string> = {
  high:   'bg-red-400',
  medium: 'bg-yellow-400',
  low:    'bg-slate-500',
};

function NewsItemRow({ item }: { item: NewsItem }) {
  return (
    <div className="flex gap-3 py-2.5 border-b border-slate-700/50 last:border-0">
      <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${IMPORTANCE_DOT[item.importance] ?? 'bg-slate-500'}`} />
      <div className="flex-1 min-w-0">
        {item.url ? (
          <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-sm text-slate-200 hover:text-blue-300 leading-snug line-clamp-2">
            {item.title}
          </a>
        ) : (
          <div className="text-sm text-slate-200 leading-snug line-clamp-2">{item.title}</div>
        )}
        <div className="flex gap-2 mt-1 items-center flex-wrap">
          <span className={`text-xs px-1.5 py-0.5 rounded border ${SENTIMENT_BADGE[item.sentiment]}`}>{item.sentiment}</span>
          {item.source && <span className="text-xs text-slate-500">{item.source}</span>}
          {item.category !== 'other' && <span className="text-xs text-slate-500 capitalize">{item.category}</span>}
        </div>
      </div>
    </div>
  );
}

interface Props {
  news: NewsSummary;
}

export function NewsSection({ news }: Props) {
  const positive = news.items.filter(i => i.sentiment === 'positive');
  const negative = news.items.filter(i => i.sentiment === 'negative');
  const neutral  = news.items.filter(i => i.sentiment === 'neutral');

  const scoreColor = news.news_score >= 65 ? 'text-green-400' : news.news_score >= 45 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-slate-200 font-semibold">News & Sentiment</h3>
        <span className={`text-lg font-bold font-mono ${scoreColor}`}>{news.news_score.toFixed(0)}/100</span>
      </div>

      <div className="flex gap-4 mb-4 text-sm">
        <span className="text-green-400">↑ {news.positive_count} positive</span>
        <span className="text-slate-400">― {news.neutral_count} neutral</span>
        <span className="text-red-400">↓ {news.negative_count} negative</span>
      </div>

      {news.coverage_limited && (
        <div className="text-xs text-yellow-500 bg-yellow-900/20 border border-yellow-800 rounded px-3 py-1.5 mb-4">
          Limited coverage — using yfinance news data
        </div>
      )}

      {news.items.length === 0 ? (
        <p className="text-sm text-slate-500">No news items available.</p>
      ) : (
        <div>
          {positive.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-green-400 font-semibold mb-1 uppercase tracking-wider">Positive</div>
              {positive.slice(0, 5).map((item, i) => <NewsItemRow key={i} item={item} />)}
            </div>
          )}
          {negative.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-red-400 font-semibold mb-1 uppercase tracking-wider">Negative</div>
              {negative.slice(0, 5).map((item, i) => <NewsItemRow key={i} item={item} />)}
            </div>
          )}
          {neutral.length > 0 && (
            <div>
              <div className="text-xs text-slate-400 font-semibold mb-1 uppercase tracking-wider">Neutral</div>
              {neutral.slice(0, 3).map((item, i) => <NewsItemRow key={i} item={item} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
