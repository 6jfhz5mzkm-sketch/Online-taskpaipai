
// MySQL 连接（mysql2/promise）
import mysql from 'mysql2/promise';
import { config } from './config.js';

let pool = null;
export function getPool() {
  if (!pool) {
    pool = mysql.createPool({
      ...config.db,
      waitForConnections: true,
      connectionLimit: 5,
      charset: 'utf8mb4',
      namedPlaceholders: false,
      dateStrings: true,
    });
  }
  return pool;
}

export async function q(sql, params = []) {
  const [rows] = await getPool().query(sql, params);
  return rows;
}
