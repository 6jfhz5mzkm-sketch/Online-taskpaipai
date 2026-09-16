/**
 * 商品发布（T2.2）任务图片示例映射
 *
 * @description taskId → 图片路径数组（src/static/images/product-guide/ 下，构建自动打包）。
 *              图片来自用户提供的「Upload information」目录，文件名已按方案映射表英文重命名。
 *              T2.2.9 设置商品服务、T2.2.13 提交商品审核 无对应图片 → 不在映射中（任务卡片不显示按钮）；
 *              T2.2.14 修改商品（3 张图，映射表外补充，来源目录同名文件）。
 */
export const PRODUCT_GUIDE_IMAGES: Record<string, string[]> = {
  'T2.2.1': [
    '/static/images/product-guide/guide-process-1.png',
    '/static/images/product-guide/guide-process-2.png',
  ],
  'T2.2.2': ['/static/images/product-guide/guide-category-1.png'],
  'T2.2.3': ['/static/images/product-guide/guide-basic-info-1.png'],
  'T2.2.4': [
    '/static/images/product-guide/guide-attr-required.png',
    '/static/images/product-guide/guide-attr-important-1.png',
    '/static/images/product-guide/guide-attr-important-2.png',
  ],
  'T2.2.5': ['/static/images/product-guide/guide-upload-1.png'],
  'T2.2.6': ['/static/images/product-guide/guide-sales-attr-1.png'],
  'T2.2.7': [
    '/static/images/product-guide/guide-desc-1.png',
    '/static/images/product-guide/guide-desc-2.gif',
    '/static/images/product-guide/guide-desc-detail-3.png',
  ],
  'T2.2.8': ['/static/images/product-guide/guide-logistics-1.png'],
  'T2.2.10': ['/static/images/product-guide/guide-function-1.png'],
  'T2.2.11': [
    '/static/images/product-guide/guide-assistant-1.png',
    '/static/images/product-guide/guide-assistant-2.png',
    '/static/images/product-guide/guide-assistant-3.png',
  ],
  'T2.2.12': [
    '/static/images/product-guide/guide-draft-1.png',
    '/static/images/product-guide/guide-draft-2.png',
  ],
  'T2.2.14': [
    '/static/images/product-guide/guide-edit-1.png',
    '/static/images/product-guide/guide-edit-2.png',
    '/static/images/product-guide/guide-edit-3.png',
  ],
};
