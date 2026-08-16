"""
数据库自修复模块 - 启动时检查并修复数据库
"""
import os
import sqlite3
import shutil

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge.db')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'db_backups')


def _get_logger():
    from utils.logger import get_logger
    return get_logger('repair')


def _backup_corrupted(corrupted_path):
    """备份损坏的数据库文件"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    import datetime
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'corrupted_{ts}.db')
    shutil.copy2(corrupted_path, backup_path)
    return backup_path


def _check_db_integrity(db_path):
    """检查数据库完整性，返回 (is_valid, error_message)"""
    if not os.path.exists(db_path):
        return False, 'database file not found'

    # 文件太小时肯定损坏
    if os.path.getsize(db_path) < 4096:
        return False, 'database file too small ({} bytes)'.format(os.path.getsize(db_path))

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查完整性
        cursor.execute('PRAGMA integrity_check')
        result = cursor.fetchone()
        if result[0] != 'ok':
            conn.close()
            return False, 'integrity check failed: ' + str(result[0])

        # 检查关键表是否存在
        required_tables = ['categories', 'knowledge_points', 'tags', 'knowledge_tags']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
        missing = [t for t in required_tables if t not in existing]
        if missing:
            conn.close()
            return False, 'missing tables: ' + ', '.join(missing)

        conn.close()
        return True, 'ok'
    except sqlite3.Error as e:
        return False, 'sqlite error: ' + str(e)


def _cleanup_wal(db_path):
    """清理孤立的 WAL/SHM 文件"""
    wal_path = db_path + '-wal'
    shm_path = db_path + '-shm'
    for p in [wal_path, shm_path]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def repair_database():
    """启动时自修复数据库"""
    log = _get_logger()
    log.info('=== 数据库自检开始 ===')

    valid, msg = _check_db_integrity(DB_PATH)

    if valid:
        _cleanup_wal(DB_PATH)
        log.info('数据库健康: %s', msg)
        log.info('=== 数据库自检完成（正常）===')
        return True

    log.warning('数据库异常: %s', msg)

    # 备份损坏文件
    if os.path.exists(DB_PATH):
        backup = _backup_corrupted(DB_PATH)
        log.info('已备份损坏数据库到: %s', backup)

    # 删除损坏文件
    _cleanup_wal(DB_PATH)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        log.info('已删除损坏数据库文件')

    # 重建数据库
    log.info('重建数据库...')
    try:
        from models.database import Database
        db = Database()
        db.init_db()
        log.info('数据库重建成功')
    except Exception as e:
        log.critical('数据库重建失败: %s', str(e))
        log.info('=== 数据库自检完成（失败）===')
        return False

    log.info('=== 数据库自检完成（已修复）===')
    return True