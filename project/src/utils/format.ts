/**
 * 格式化工具函数
 */

/** 格式化日期 */
export const formatDate = (date: string | Date, format = 'YYYY-MM-DD'): string => {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');

  return format
    .replace('YYYY', String(year))
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes);
};

/** 格式化数字（千分位） */
export const formatNumber = (num: number): string => {
  return num.toLocaleString('zh-CN');
};

/** 格式化进度百分比 */
export const formatPercent = (current: number, total: number): number => {
  if (total === 0) return 0;
  return Math.round((current / total) * 100);
};
