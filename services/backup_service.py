import json
import os
import shutil
import datetime
from models.database import Database
from utils.logger import get_logger

logger = get_logger('backup_service')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')


class BackupService:
    def __init__(self):
        self.db = Database()
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def list_backups(self):
        """列出所有备份"""
        backups = []
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if f.endswith('.db'):
                path = os.path.join(BACKUP_DIR, f)
                note = ''
                meta_path = path + '.meta.json'
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as mf:
                        meta = json.load(mf)
                        note = meta.get('note', '')
                backups.append({
                    'filename': f,
                    'size': os.path.getsize(path),
                    'note': note,
                    'created_at': datetime.datetime.fromtimestamp(
                        os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
                })
        return backups

    def create_backup(self, note=''):
        """创建全量备份"""
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        # 文件名包含备注
        safe_note = ''.join(c for c in note if c.isalnum() or c in '._- ') if note else ''
        if safe_note:
            filename = 'backup_{}_{}.db'.format(ts, safe_note[:30])
        else:
            filename = 'backup_{}.db'.format(ts)
        # 先确保 WAL 写入主文件
        self.db.checkpoint()
        # 关闭数据库连接
        self.db.close()
        # 复制数据库文件
        db_path = Database._db_path
        dest = os.path.join(BACKUP_DIR, filename)
        shutil.copy2(db_path, dest)
        # 保存备注到 json 文件
        if note:
            meta_path = dest + '.meta.json'
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({'note': note, 'created_at': ts}, f, ensure_ascii=False)
        logger.info('创建备份 %s note=%s', filename, note)
        return {'filename': filename, 'path': dest}

    def restore_backup(self, filename):
        """恢复备份"""
        src = os.path.join(BACKUP_DIR, filename)
        if not os.path.exists(src):
            return False
        db_path = Database._db_path
        # 备份当前数据库
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2(db_path, os.path.join(BACKUP_DIR, 'pre_restore_{}.db'.format(ts)))
        # 关闭连接
        self.db.close()
        # 恢复
        shutil.copy2(src, db_path)
        # 写入重启标记
        restart_flag = os.path.join(os.path.dirname(db_path), '.restart')
        with open(restart_flag, 'w') as f:
            f.write('1')
        logger.info('恢复备份 %s', filename)
        return True

    def delete_backup(self, filename):
        """删除备份"""
        path = os.path.join(BACKUP_DIR, filename)
        if os.path.exists(path):
            os.remove(path)
            meta_path = path + '.meta.json'
            if os.path.exists(meta_path):
                os.remove(meta_path)
            logger.info('删除备份 %s', filename)
            return True
        return False