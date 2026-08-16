from models.database import Database
from models.category import Category
from utils.logger import get_logger

logger = get_logger('category_service')


class CategoryService:
    def __init__(self):
        self.db = Database()

    def create(self, name, description=''):
        cursor = self.db.execute_write(
            'INSERT INTO categories (name, description) VALUES (?, ?)',
            (name, description)
        )
        category_id = cursor.lastrowid
        row = self.db.execute_read_one('SELECT * FROM categories WHERE id = ?', (category_id,))
        logger.info('创建分类 id=%s name=%s', category_id, name)
        return Category.from_row(row)

    def get_all(self):
        rows = self.db.execute_read(
            '''SELECT c.*, COUNT(kp.id) as knowledge_count
               FROM categories c
               LEFT JOIN knowledge_points kp ON c.id = kp.category_id
               GROUP BY c.id
               ORDER BY c.created_at DESC'''
        )
        result = []
        for row in rows:
            cat = Category.from_row(row)
            d = cat.to_dict()
            d['knowledge_count'] = row['knowledge_count']
            result.append(d)
        return result

    def get_by_id(self, category_id):
        row = self.db.execute_read_one('SELECT * FROM categories WHERE id = ?', (category_id,))
        if row:
            return Category.from_row(row)
        return None

    def update(self, category_id, name=None, description=None):
        # 保护"未分类"不可改名
        cat = self.get_by_id(category_id)
        if cat and cat.name == '未分类' and name is not None and name != '未分类':
            return None
        fields = []
        values = []
        if name is not None:
            fields.append('name = ?')
            values.append(name)
        if description is not None:
            fields.append('description = ?')
            values.append(description)
        if not fields:
            return None
        values.append(category_id)
        self.db.execute_write(
            'UPDATE categories SET %s WHERE id = ?' % ', '.join(fields),
            values
        )
        row = self.db.execute_read_one('SELECT * FROM categories WHERE id = ?', (category_id,))
        logger.info('更新分类 id=%s', category_id)
        return Category.from_row(row) if row else None

    def delete(self, category_id):
        # 保护"未分类"不可删除
        cat = self.get_by_id(category_id)
        if cat and cat.name == '未分类':
            return False
        # 查询受影响的 knowledge_points
        rows = self.db.execute_read('SELECT id FROM knowledge_points WHERE category_id = ?', (category_id,))
        affected_kp_ids = [r['id'] for r in rows]
        before = {
            'id': cat.id, 'name': cat.name, 'description': cat.description
        }
        # 先获取"未分类"的 ID
        uncat = self.db.execute_read_one("SELECT id FROM categories WHERE name = '未分类'", ())
        uncat_id = uncat['id'] if uncat else None
        # 如果"未分类"不存在，先创建
        if uncat_id is None:
            cursor = self.db.execute_write("INSERT INTO categories (name, description) VALUES ('未分类', '默认分类')")
            uncat_id = cursor.lastrowid
        # 迁移知识点
        self.db.execute_write(
            "UPDATE knowledge_points SET category_id = ? WHERE category_id = ?",
            (uncat_id, category_id))
        # 再删除分类
        cursor = self.db.execute_write('DELETE FROM categories WHERE id = ?', (category_id,))
        affected = cursor.rowcount
        if affected > 0:
            from services.operation_service import OperationService
            op = OperationService()
            op.log_operation('delete', 'category', category_id, cat.name,
                before_state=before, affected_ids=affected_kp_ids)
            logger.info('删除分类 id=%s name=%s 影响知识点=%s', category_id, cat.name, len(affected_kp_ids))
        return affected > 0