import axios from 'axios';
import type { AnalysisRequest, StockAnalysisResult } from '../types/stock';

const client = axios.create({ baseURL: '/api' });

export async function analyzeStock(req: AnalysisRequest): Promise<StockAnalysisResult> {
  const { data } = await client.post<StockAnalysisResult>('/stocks/analyze', {
    ticker: req.ticker.toUpperCase(),
    horizons: req.horizons ?? ['short_term', 'medium_term', 'long_term'],
    risk_profile: req.risk_profile ?? 'moderate',
  });
  return data;
}
