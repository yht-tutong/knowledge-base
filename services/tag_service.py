from models.database import Database
from models.tag import Tag
from utils.logger import get_logger

logger = get_logger('tag_service')


class TagService:
    def __init__(self):
        self.db = Database()

    def create(self, name, shape='ellipse', color=''):
        cursor = self.db.execute_write(
            'INSERT INTO tags (name, shape, color) VALUES (?, ?, ?)',
            (name, shape, color)
        )
        tag_id = cursor.lastrowid
        row = self.db.execute_read_one('SELECT * FROM tags WHERE id = ?', (tag_id,))
        logger.info('创建标签 id=%s name=%s', tag_id, name)
        return Tag.from_row(row)

    def get_all(self):
        rows = self.db.execute_read('SELECT * FROM tags ORDER BY created_at DESC')
        return [Tag.from_row(row).to_dict() for row in rows]

    def get_by_id(self, tag_id):
        row = self.db.execute_read_one('SELECT * FROM tags WHERE id = ?', (tag_id,))
        return Tag.from_row(row)

    def delete(self, tag_id):
        tag = self.get_by_id(tag_id)
        tag_name = tag.name if tag else 'unknown'
        cursor = self.db.execute_write('DELETE FROM tags WHERE id = ?', (tag_id,))
        affected = cursor.rowcount
        if affected > 0:
            logger.info('删除标签 id=%s name=%s', tag_id, tag_name)
        return affected > 0

    def batch_delete(self, tag_ids):
        """批量删除标签"""
        if not tag_ids:
            return 0
        placeholders = ','.join(['?'] * len(tag_ids))
        cursor = self.db.execute_write(
            'DELETE FROM tags WHERE id IN (' + placeholders + ')',
            tuple(tag_ids))
        count = cursor.rowcount
        logger.info('批量删除标签 count=%s ids=%s', count, tag_ids)
        return count