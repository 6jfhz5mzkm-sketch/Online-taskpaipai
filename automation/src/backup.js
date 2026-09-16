
// 数据库备份：每次 --apply 写库前执行 mysqldump，备份失败则中止写库
import { execFile } from 'child_process';
import { promisify } from 'util';
import { mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { config } from './config.js';

const execFileP = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
// 默认备份目录：automation/backups（可用 FEE_BACKUP_DIR 覆盖）
const AUTO_DIR = path.resolve(__dirname, '..');
const BACKUP_DIR = path.resolve(process.env.FEE_BACKUP_DIR || path.join(AUTO_DIR, 'backups'));

function stamp() {
  return new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
}

// 执行备份，返回备份文件路径
export async function backupDatabase() {
  const db = config.db;
  mkdirSync(BACKUP_DIR, { recursive: true });
  const file = path.join(BACKUP_DIR, db.database + '-' + stamp() + '.sql');
  const dumpCmd = process.env.MYSQL_DUMP || 'mysqldump';
  const args = [
    '-h', db.host,
    '-P', String(db.port),
    '-u', db.user,
    // key: 强制 utf8mb4，避免中文字段再次乱码
    '--default-character-set=utf8mb4',
    '--single-transaction',   // InnoDB 一致快照，不长时间锁表
    '--routines',
    '--triggers',
    db.database,
    '--result-file', file,
  ];
  // 密码通过环境变量 MYSQL_PWD 传入，避免出现在进程命令行
  const env = { ...process.env, MYSQL_PWD: db.password || '' };
  try {
    await execFileP(dumpCmd, args, { env, maxBuffer: 1024 * 1024 * 512 });
  } catch (e) {
    const err = (e.stderr || e.message || '').toString();
    throw new Error('数据库备份失败，为安全起见中止写库。' + err);
  }
  return { file, dir: BACKUP_DIR };
}

// 供手动备份用：node src/index.js --backup-only
export { BACKUP_DIR };
