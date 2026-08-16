import json
from models.database import Database
from utils.logger import get_logger

logger = get_logger('operation_service')
MAX_OPERATIONS = 500


class OperationService:
    def __init__(self):
        self.db = Database()

    def _get_valid_category_id(self, cursor, category_id):
        """验证分类是否存在，不存在则返回'未分类'的 id"""
        if category_id is None:
            return self._get_uncategorized_id(cursor)
        cursor.execute('SELECT id FROM categories WHERE id = ?', (category_id,))
        if cursor.fetchone():
            return category_id
        return self._get_uncategorized_id(cursor)

    def _get_uncategorized_id(self, cursor):
        cursor.execute("SELECT id FROM categories WHERE name = '未分类'")
        row = cursor.fetchone()
        if row:
            return row['id']
        cursor.execute("SELECT id FROM categories ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        return row['id'] if row else 1

    def log_operation(self, op_type, entity_type, entity_id, entity_name='',
                      before_state=None, after_state=None, affected_ids=None):
        self.db.execute_write(
            '''INSERT INTO operation_logs (op_type, entity_type, entity_id, entity_name,
               before_state, after_state, affected_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (op_type, entity_type, entity_id, entity_name,
             json.dumps(before_state or {}, ensure_ascii=False),
             json.dumps(after_state or {}, ensure_ascii=False),
             json.dumps(affected_ids or [], ensure_ascii=False))
        )
        # 清理超出限制的旧记录
        self.db.execute_write(
            'DELETE FROM operation_logs WHERE id NOT IN '
            '(SELECT id FROM operation_logs ORDER BY id DESC LIMIT ?)',
            (MAX_OPERATIONS,)
        )
        logger.info('操作记录 type=%s entity=%s/%s name=%s', op_type, entity_type, entity_id, entity_name)

    def get_recent(self, limit=50):
        """获取最近操作记录"""
        rows = self.db.execute_read(
            'SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?',
            (limit,)
        )
        result = []
        for row in rows:
            result.append({
                'id': row['id'], 'op_type': row['op_type'],
                'entity_type': row['entity_type'], 'entity_id': row['entity_id'],
                'entity_name': row['entity_name'],
                'before_state': json.loads(row['before_state']),
                'after_state': json.loads(row['after_state']),
                'affected_ids': json.loads(row['affected_ids']),
                'created_at': row['created_at']
            })
        return result

    def undo_operation(self, op_id):
        """撤销操作"""
        row = self.db.execute_read_one('SELECT * FROM operation_logs WHERE id = ?', (op_id,))
        if not row:
            return False, '操作记录不存在'

        op_type = row['op_type']
        entity_type = row['entity_type']
        before_state = json.loads(row['before_state'])
        after_state = json.loads(row['after_state'])

        def do_undo(cursor):
            if op_type == 'create' and entity_type == 'knowledge':
                # 撤销创建 = 删除知识点
                cursor.execute('DELETE FROM knowledge_points WHERE id = ?', (row['entity_id'],))
            elif op_type == 'update' and entity_type == 'knowledge':
                # 撤销更新 = 恢复 before_state
                bs = before_state
                valid_cat = self._get_valid_category_id(cursor, bs.get('category_id'))
                cursor.execute(
                    'UPDATE knowledge_points SET title=?, content=?, category_id=? WHERE id=?',
                    (bs.get('title', ''), bs.get('content', ''), valid_cat, row['entity_id'])
                )
                # 恢复标签
                cursor.execute('DELETE FROM knowledge_tags WHERE knowledge_id = ?', (row['entity_id'],))
                for tag_id in bs.get('tag_ids', []):
                    cursor.execute(
                        'INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)',
                        (row['entity_id'], tag_id)
                    )
            elif op_type == 'delete' and entity_type == 'knowledge':
                # 撤销删除 = 重新创建知识点
                bs = before_state
                valid_cat = self._get_valid_category_id(cursor, bs.get('category_id'))
                cursor.execute(
                    'INSERT INTO knowledge_points (id, title, content, category_id, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    (bs.get('id'), bs.get('title', ''), bs.get('content', ''),
                     valid_cat, bs.get('created_at'), bs.get('updated_at'))
                )
                for tag_id in bs.get('tag_ids', []):
                    cursor.execute(
                        'INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)',
                        (bs.get('id'), tag_id)
                    )
            elif op_type == 'batch_delete' and entity_type == 'knowledge':
                # 批量删除的撤销
                affected = json.loads(row['affected_ids'])
                for item in affected:
                    bs = item.get('before_state', item) if isinstance(item, dict) else {}
                    kp_id = bs.get('id')
                    if not kp_id:
                        continue
                    title = bs.get('title', '')
                    content = bs.get('content', '')
                    valid_cat = self._get_valid_category_id(cursor, bs.get('category_id'))
                    created_at = bs.get('created_at')
                    updated_at = bs.get('updated_at')
                    cursor.execute(
                        'INSERT INTO knowledge_points (id, title, content, category_id, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?)',
                        (kp_id, title, content, valid_cat, created_at, updated_at)
                    )
                    for tag_id in bs.get('tag_ids', []):
                        cursor.execute(
                            'INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)',
                            (kp_id, tag_id)
                        )
            elif op_type == 'import' and entity_type == 'knowledge':
                # 撤销导入 = 删除所有导入的知识点
                affected = json.loads(row['affected_ids'])
                for kp_id in affected:
                    cursor.execute('DELETE FROM knowledge_points WHERE id = ?', (kp_id,))
            elif op_type == 'delete' and entity_type == 'category':
                # 撤销删除分类 = 重建分类（如不存在）+ 恢复知识点分类
                bs = before_state
                cat_id = bs.get('id')
                cat_name = bs.get('name', '')
                # 尝试用原 ID 插入
                cursor.execute('INSERT OR IGNORE INTO categories (id, name, description) VALUES (?, ?, ?)',
                    (cat_id, cat_name, bs.get('description', '')))
                # 如果原 ID 已存在但名称不同，通过名称查找
                cursor.execute('SELECT id FROM categories WHERE id = ?', (cat_id,))
                if not cursor.fetchone():
                    cursor.execute('SELECT id FROM categories WHERE name = ?', (cat_name,))
                    existing = cursor.fetchone()
                    if existing:
                        cat_id = existing['id']
                # 恢复该分类下的知识点
                affected = json.loads(row['affected_ids'])
                for kp_id in affected:
                    cursor.execute(
                        'UPDATE knowledge_points SET category_id = ? WHERE id = ?',
                        (cat_id, kp_id)
                    )
            else:
                raise ValueError('不支持撤销此操作类型: ' + op_type + '/' + entity_type)

        try:
            self.db.execute_transaction(do_undo)
            # 撤销成功后删除该操作记录
            self.db.execute_write('DELETE FROM operation_logs WHERE id = ?', (op_id,))
            logger.info('撤销操作 id=%s type=%s entity=%s', op_id, op_type, entity_type)
            return True, '撤销成功'
        except ValueError as e:
            logger.error('撤销操作失败 id=%s error=%s', op_id, str(e))
            return False, str(e)
        except Exception as e:
            logger.error('撤销操作失败 id=%s error=%s', op_id, str(e))
            return False, str(e) if str(e).startswith('撤销失败') else '撤销失败: ' + str(e)

    def undo_from(self, op_id):
        """级联撤销：撤销该操作及之后所有操作，成功后删除所有被撤销的记录"""
        rows = self.db.execute_read(
            'SELECT id FROM operation_logs WHERE id >= ? ORDER BY id DESC',
            (op_id,)
        )
        if not rows:
            return False, '操作记录不存在'

        errors = []
        undone_ids = []
        for r in rows:
            ok, msg = self.undo_operation(r['id'])
            if ok:
                undone_ids.append(r['id'])
            else:
                errors.append('操作%s: %s' % (r['id'], msg))

        if errors:
            return False, '; '.join(errors)
        return True, '已撤销 %s 条操作' % len(undone_ids)