/**
 * API 统一导出
 */
export {
  searchTrademark,
  fetchShopSummary,
  fetchShopAnalysis,
  saveShopStarData,
  saveProductCountData,
  saveHealthScoreData,
  uploadShopExcel,
} from './stage2';
export type {
  TrademarkResult,
  ShopStarData,
  ProductCountData,
  HealthScoreData,
  ShopSummaryData,
  ShopSummaryTimeRange,
  ShopAnalysisData,
  ShopAnalysisPoint,
  ShopAnalysisSuggestion,
} from './stage2';
