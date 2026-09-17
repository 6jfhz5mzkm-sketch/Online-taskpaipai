/**
 * 阶段二（开店搭建）接口
 * @description 商标搜索 / Excel 上传 / 店铺数据表单保存；路径与后端模块对齐，
 *              字段名与后端 DTO 对齐（merchant_id 由后端从 JWT 取，前端不传）。
 */
import request, { BASE_URL } from './request';

/** 商标搜索结果 */
export interface TrademarkResult {
  brand_name: string;
  registration_number: string;
}

/** 店铺星级数据（T2.5.1，POST /api/shop/star） */
export interface ShopStarData {
  shopStar: number;
  serviceScore?: number;
  logisticsScore?: number;
  afterSaleScore?: number;
  productScore?: number;
  dataDate: string;
}

/** 商品数量数据（T2.5.5，POST /api/shop/product-count） */
export interface ProductCountData {
  totalCount: number;
  onSaleCount?: number;
  offSaleCount?: number;
  auditCount?: number;
  dataDate: string;
}

/** 商品信息健康分数据（T2.5.6，POST /api/shop/health-score） */
export interface HealthScoreData {
  avgScore: number;
  scoreGte90Count?: number;
  score78_90Count?: number;
  score60_77Count?: number;
  scoreLt60Count?: number;
  dataDate: string;
}

/**
 * Excel 导入的逐行问题条目（#PB-24-2 契约，#PB-24-3 前端消费）
 * @description reason 为后端英文枚举（仅日志/排查用，**不直接展示**）；
 *              展示文案一律用后端 `message`（口语化中文，单一真源在后端 ISSUE_MESSAGES）。
 */
export interface ShopExcelIssue {
  /** Excel **物理行号**（表头 = 1） */
  row: number;
  /** 库列名（前端可经 SHOP_METRIC_LABELS 映射为中文名，未收录则回退列名） */
  field: string;
  /** 原值（后端已截断 40 字，可缺省） */
  value?: string | null;
  /** 原因枚举（英文，后端唯一真源，不直接展示） */
  reason: string;
  /** 处置动作：skipped=该行已跳过；normalized=该值已归一 */
  action?: 'skipped' | 'normalized' | string;
  /** 用户可读中文原因（后端下发，前端**原样展示**，不得另造文案） */
  message: string;
}

/**
 * Excel 上传结果（#PB-24-2 契约；字段全部可选以兼容老响应/空 data）
 * @description HTTP 201（有写入）或 200（全部行皆坏、count=0）均为**成功响应**；
 *              计数为**全量**，issues 最多 200 条（超出时 issues_truncated=true，完整清单进服务端日志）。
 */
export interface ShopExcelUploadResult {
  success?: boolean;
  /** 实际写入行数 */
  count?: number;
  /** 数据区非全空行数 */
  total_rows?: number;
  /** 坏行数（全量） */
  skipped?: number;
  /** 被归一的字段数（全量） */
  normalized?: number;
  /** 逐行问题清单（最多 200 条） */
  issues?: ShopExcelIssue[];
  /** 问题是否被截断（true = issues 只回了前 200 条） */
  issues_truncated?: boolean;
}

/** 数据看板时间维度 */
export type ShopSummaryTimeRange = 'yesterday' | '7d' | '30d';

/**
 * 数据看板汇总（GET /api/shop/summary）
 * @description 契约预留：由总控另行派后端单实现；字段为 shop_* 表实体字段（snake_case），
 *              各类型可能返回 null（该类型暂无数据）或整体 404（接口未就绪）。
 */
export interface ShopSummaryData {
  time_range?: ShopSummaryTimeRange;
  star?: Record<string, number | string> | null;
  trade?: Record<string, number | string> | null;
  traffic?: Record<string, number | string> | null;
  product?: Record<string, number | string> | null;
  product_count?: Record<string, number | string> | null;
  health_score?: Record<string, number | string> | null;
}

/** 做得好/待改进条目（point + 数据依据 reason） */
export interface ShopAnalysisPoint {
  point: string;
  reason: string;
}

/** 建议条目（action + 优先级） */
export interface ShopAnalysisSuggestion {
  action: string;
  priority: 'high' | 'medium' | 'low';
}

/** AI 经营分析结果（POST /api/shop/analysis） */
export interface ShopAnalysisData {
  /** 现状总结 */
  summary: string;
  /** 做得好（{ point, reason } 对象数组） */
  strengths: ShopAnalysisPoint[];
  /** 待改进（{ point, reason } 对象数组） */
  weaknesses: ShopAnalysisPoint[];
  /** 建议（{ action, priority } 对象数组，按优先级从高到低） */
  suggestions: ShopAnalysisSuggestion[];
}

/** 商标模糊搜索（T2.1.2） */
export const searchTrademark = (keyword: string) => {
  return request.get<TrademarkResult[]>('/api/trademark/search', { data: { keyword } });
};

/** 数据看板聚合查询（时间维度：yesterday/7d/30d） */
export const fetchShopSummary = (timeRange: ShopSummaryTimeRange) => {
  return request.get<ShopSummaryData>('/api/shop/summary', { data: { time_range: timeRange } });
};

/** 触发 AI 经营分析（当前时间维度，契约预留待后端实现） */
export const fetchShopAnalysis = (timeRange: ShopSummaryTimeRange) => {
  return request.post<ShopAnalysisData>(`/api/shop/analysis?time_range=${timeRange}`);
};

/** 商家顾问企微二维码地址（预留后端静态接口，参考阶段一 T1.3.8） */
export const getAdvisorQrCodeUrl = () => `${BASE_URL}/api/static/advisor-qr.jpg`;

/** 清除当前商家全部店铺数据（F2-DC：POST /api/shop/clear-data；清除 shop_* 表 + 重置 T2.5 完成态，保留解锁；待后端就绪联调） */
export const clearShopData = () =>
  request.post<{ ok?: boolean }>('/api/shop/clear-data', {}).then((res) => res.data);

/** 保存店铺星级数据（T2.5.1） */
export const saveShopStarData = (data: ShopStarData) => {
  return request.post('/api/shop/star', data);
};

/** 保存商品数量数据（T2.5.5） */
export const saveProductCountData = (data: ProductCountData) => {
  return request.post('/api/shop/product-count', data);
};

/** 保存商品信息健康分数据（T2.5.6） */
export const saveHealthScoreData = (data: HealthScoreData) => {
  return request.post('/api/shop/health-score', data);
};

/* ---------- H5 端 multipart 上传（唯一实现，uploadShopExcel / optimizeMainImage 共用） ---------- */

// #ifdef H5
/** H5 端 multipart 上传参数（结构化：接口路径、文件名与 MIME 推断全部显式传入） */
interface H5MultipartUploadOptions<T> {
  /** 上传接口路径（以 / 开头），请求地址 = BASE_URL + path */
  path: string;
  /** blob URL（uni.chooseFile / uni.chooseImage 返回值） */
  filePath: string;
  /** multipart 文件名主干，最终文件名 = fileBaseName + '.' + ext */
  fileBaseName: string;
  /** filePath 无法解析出扩展名时的兜底扩展名 */
  fallbackExt: string;
  /** blob.type 为空时按扩展名推断 MIME（可选：接口只接受单一格式时无需分派） */
  mimeByExt?: Record<string, string>;
  /** mimeByExt 未命中时的默认 MIME */
  defaultMime: string;
  /** code===0 但响应无 data 时的兜底返回值；不传则要求响应必须带 data 才算成功 */
  emptyDataFallback?: T;
  /** 无后端 message 时（如非 JSON 响应）的兜底错误文案，最终形式为「文案（状态码）」 */
  defaultErrorMessage: string;
}

/**
 * H5 端 multipart 文件上传（blob URL → File → FormData → fetch，带 Bearer token）
 * @description P1-01：uni.chooseFile/uni.chooseImage 在 H5 返回 blob URL，uni.uploadFile
 *              无法可靠上传（ERR_FILE_NOT_FOUND，请求未达后端），故 H5 端统一走原生 fetch；
 *              非 H5（小程序）仍由各接口保留 uni.uploadFile 分支。
 */
const uploadFileViaFetch = <T>(options: H5MultipartUploadOptions<T>): Promise<T> => {
  const { path, filePath, fileBaseName, fallbackExt, mimeByExt, defaultMime, emptyDataFallback, defaultErrorMessage } = options;
  return (async () => {
    const token = uni.getStorageSync('token');
    try {
      const blob = await (await fetch(filePath)).blob();
      const extMatch = /\.([a-zA-Z0-9]+)$/.exec(filePath);
      const ext = extMatch ? extMatch[1].toLowerCase() : fallbackExt;
      const mime = blob.type || mimeByExt?.[ext] || defaultMime;
      const form = new FormData();
      form.append('file', new File([blob], fileBaseName + '.' + ext, { type: mime }));
      const res = await fetch(BASE_URL + path, {
        method: 'POST',
        headers: token ? { Authorization: 'Bearer ' + token } : {},
        body: form,
      });
      const text = await res.text();
      let data: { code?: number; message?: string; data?: T } | null = null;
      try {
        data = JSON.parse(text);
      } catch {
        data = null;
      }
      if (data && data.code === 0) {
        if (data.data) return data.data as T;
        if (emptyDataFallback !== undefined) return emptyDataFallback;
      }
      // B13：后端可读 message 原样透传；非 JSON 响应（网关/代理 HTML 错误页）不再拼接原始 body
      //      片段，仅保留状态码，避免对外泄漏内部页面/堆栈信息
      throw new Error(data?.message || defaultErrorMessage + '（' + res.status + '）');
    } catch (e) {
      throw new Error((e as Error)?.message || '网络连接失败，请重试');
    }
  })();
};
// #endif

/** 上传 Excel（T2.5.2~T2.5.4，multipart 字段仅 file，带 token header）
 *  P1-01 修复：H5 端 uni.chooseFile 返回 blob URL，uni.uploadFile 无法可靠上传
 *  （ERR_FILE_NOT_FOUND，请求未达后端）；H5 端复用 uploadFileViaFetch（blob → File → FormData）。
 *  非 H5（小程序）：保留 uni.uploadFile。
 *  #F-30：移除从未被调用方传入的死参数 timeRange（时间范围由后端按文件区间自行推导，见 #PB-24-2）。
 */
export const uploadShopExcel = (
  type: 'trade' | 'traffic' | 'product',
  filePath: string,
): Promise<ShopExcelUploadResult> => {
  // #ifdef H5
  return uploadFileViaFetch<ShopExcelUploadResult>({
    path: '/api/shop/' + type,
    filePath,
    fileBaseName: 'upload',
    fallbackExt: 'xlsx',
    // 仅 OOXML .xlsx：与后端 EXCEL_MIME 一致（后端已移除 .xls，返回 400「仅支持 .xlsx 文件」），
    // 选择器同样只接受 .xlsx，故无需按扩展名分派 MIME
    defaultMime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    emptyDataFallback: { success: true },
    defaultErrorMessage: '上传失败',
  });
  // #endif
  // #ifndef H5
  return new Promise<ShopExcelUploadResult>((resolve, reject) => {
    const token = uni.getStorageSync('token');
    uni.uploadFile({
      url: BASE_URL + '/api/shop/' + type,
      filePath,
      name: 'file',
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success: (res) => {
        try {
          const data = JSON.parse(res.data);
          if (data.code === 0) {
            resolve(data.data || { success: true });
          } else {
            reject(new Error(data.message || '上传失败'));
          }
        } catch (e) {
          reject(new Error('上传响应解析失败'));
        }
      },
      fail: (err) => reject(err),
    });
  });
  // #endif
};

/* ---------- 商品主图 AI 优化（T2.3.2，POST /api/shop/image-optimize，multipart 字段 file） ---------- */

/** 问题清单条目（item + 优先级 + 优化建议） */
export interface ImageOptimizeIssue {
  item: string;
  /** 优先级：后端新值为中文「重要/一般/可选」；兼容旧值 P0/P1/P2（前端 mapPriority 容错映射） */
  priority: string;
  suggestion: string;
}

/** 优化后的构图/文案方案 */
export interface ImageOptimizePlan {
  layout: string;
  copy: string;
  action_steps: string[];
}

/** 商品主图 AI 优化结果（结构化报告：概览 + 合规核查 + 问题清单 + 优化方案） */
export interface ImageOptimizeData {
  summary: string;
  compliance: string[];
  issues: ImageOptimizeIssue[];
  plan: ImageOptimizePlan;
}

/** 上传商品主图并触发 AI 优化分析（multipart 字段 file，带 token header）
 *  H5 端：uni.chooseImage 返回 blob URL，uni.uploadFile 在 H5 无法可靠上传；
 *  H5 端复用 uploadFileViaFetch（blob → File → FormData；LLM 分析较慢 30~60s，浏览器无默认超时）。
 *  非 H5（小程序）：保留 uni.uploadFile。
 */
export const optimizeMainImage = (filePath: string) => {
  // #ifdef H5
  // 后端 400/429/502/504 等可读 message（如「图片过大」「AI 分析超时」）由 uploadFileViaFetch 完整透传
  return uploadFileViaFetch<ImageOptimizeData>({
    path: '/api/shop/image-optimize',
    filePath,
    fileBaseName: 'main-image',
    fallbackExt: 'jpg',
    mimeByExt: { png: 'image/png' },
    defaultMime: 'image/jpeg',
    defaultErrorMessage: 'AI 分析失败',
  });
  // #endif
  // #ifndef H5
  return new Promise<ImageOptimizeData>((resolve, reject) => {
    const token = uni.getStorageSync('token');
    uni.uploadFile({
      url: BASE_URL + '/api/shop/image-optimize',
      filePath,
      name: 'file',
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success: (res) => {
        try {
          const data = JSON.parse(res.data);
          if (data.code === 0) {
            resolve(data.data as ImageOptimizeData);
          } else {
            reject(new Error(data.message || 'AI 分析失败'));
          }
        } catch (e) {
          const raw = typeof res.data === 'string' ? res.data.slice(0, 200) : '';
          reject(new Error(raw ? '服务异常（' + (res.statusCode || '') + '）：' + raw : '响应解析失败'));
        }
      },
      fail: (err) => {
        const msg = (err as { errMsg?: string })?.errMsg || '';
        reject(new Error(msg || '网络连接失败，请重试'));
      },
    });
  });
  // #endif
};
/* ---------- 商品标题 AI 优化（T2.3.1，POST /api/shop/title-optimize，JSON body 无图片） ---------- */

/** 标题 AI 优化请求（generate 用品牌/型号/特点/成色/关键属性/销售属性；optimize 用现有标题） */
export interface TitleOptimizeRequest {
  /** 模式：generate 标题生成 / optimize 标题优化 */
  mode: 'generate' | 'optimize';
  /** 类目：二手手机/二手电脑整机/二手奢侈品/二手智能设备/二手办公设备/二手骑行运动/二手家电/其他 */
  category: string;
  brand?: string;
  model?: string;
  features?: string;
  condition?: string;
  keyAttrs?: string;
  saleAttrs?: string;
  currentTitle?: string;
}

/** 标题 AI 优化结果（SPU 标题 + 可选 SKU 标题 + 说明/编辑建议） */
export interface TitleOptimizeData {
  spuTitle: string;
  skuTitle?: string;
  notes?: string;
}

/** 提交商品标题 AI 生成/优化（复用 request 封装：code!==0 或网络异常时 reject 可读信息） */
export const optimizeTitle = (payload: TitleOptimizeRequest) => {
  return request.post<TitleOptimizeData>('/api/shop/title-optimize', payload as Record<string, unknown>).then((res) => res.data);
};
