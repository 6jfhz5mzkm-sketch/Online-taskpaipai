/**
 * 类目接口（真源：project/docs/后端技术方案.md §5.2）
 * @description API-05 GET /api/category/list（类目选择器：一级 / 按 parent_id 取二级）
 *              API-07 POST /api/merchant/category（任务 T1.1.2 保存经营类目 1-3 个）
 *              API-07 查询侧 GET /api/merchant/category（回显已保存经营类目）
 */
import request from './request';

/**
 * 类目节点（API-05 响应元素）
 * @description id / parent_id 按当前后端实现为字符串（api-py 显式 `str(c.id)`，注释注明
 *              「对齐 NestJS: bigint 由 mysql2 返回为字符串，前端零改动需保持一致」），
 *              而真源 §5.2 API-05 行写的是 number 且含 children —— 以当前实现为准：
 *              本类型声明为 number | string 并保留可选 children，调用方统一按字符串比较、
 *              提交时按契约转 Number。
 */
export interface CategoryNode {
  id: number | string;
  name: string;
  parent_id?: number | string | null;
  children?: CategoryNode[];
}

/** 经营类目提交项（API-07 请求参数 categories 元素） */
export interface MerchantCategoryItem {
  category_id: number;
  is_primary: boolean;
}

/** 保存经营类目结果（API-07 响应 { success: true, count: number }） */
export interface SaveMerchantCategoryResult {
  success: boolean;
  count: number;
}

/**
 * 查询类目列表（API-05）
 * @param parentId 可选：传一级类目 ID 返回其下二级类目，不传返回一级类目
 */
export const fetchCategoryList = (parentId?: number) =>
  request
    .get<CategoryNode[]>(parentId === undefined ? '/api/category/list' : `/api/category/list?parent_id=${parentId}`)
    .then((res) => res.data);

/** 保存商家经营类目（API-07；1-3 个，is_primary 唯一） */
export const saveMerchantCategories = (categories: MerchantCategoryItem[]) =>
  request.post<SaveMerchantCategoryResult>('/api/merchant/category', { categories }).then((res) => res.data);

/** 已保存经营类目项（API-07 查询侧响应 categories 元素；不含类目名称） */
export interface SavedMerchantCategory {
  category_id: number;
  is_primary: boolean;
}

/** 查询已保存经营类目结果（API-07 查询侧响应 data） */
export interface MerchantCategoryListResult {
  success: boolean;
  categories: SavedMerchantCategory[];
}

/**
 * 查询已保存经营类目（API-07 查询侧）
 * @description 无记录时后端返回空数组（code:0，非 404）；排序由后端保证
 *              `is_primary DESC, category_id ASC`（主营在前）。响应不含类目名称。
 */
export const fetchMerchantCategories = () =>
  request
    .get<MerchantCategoryListResult>('/api/merchant/category')
    .then((res) => res.data?.categories ?? []);
