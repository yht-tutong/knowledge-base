import json
from models.database import Database
from models.knowledge_point import KnowledgePoint
from services.operation_service import OperationService
from utils.logger import get_logger

logger = get_logger('knowledge_service')


class KnowledgeService:
    def __init__(self):
        self.db = Database()
        self.op_service = OperationService()

    def _get_tags_for_knowledge(self, kp_id):
        rows = self.db.execute_read(
            '''SELECT t.id, t.name, t.shape, t.created_at
               FROM tags t
               INNER JOIN knowledge_tags kt ON t.id = kt.tag_id
               WHERE kt.knowledge_id = ?
               ORDER BY t.name''',
            (kp_id,)
        )
        return [{'id': row['id'], 'name': row['name'], 'shape': row['shape'],
                 'created_at': row['created_at']} for row in rows]

    def _set_tags(self, kp_id, tag_ids):
        if tag_ids is not None:
            self.db.execute_write('DELETE FROM knowledge_tags WHERE knowledge_id = ?', (kp_id,))
            for tag_id in tag_ids:
                self.db.execute_write(
                    'INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)',
                    (kp_id, tag_id)
                )

    def create(self, title, content, category_id, tag_ids=None):
        cursor = self.db.execute_write(
            'INSERT INTO knowledge_points (title, content, category_id) VALUES (?, ?, ?)',
            (title, content, category_id)
        )
        kp_id = cursor.lastrowid
        self._set_tags(kp_id, tag_ids)
        row = self.db.execute_read_one('SELECT * FROM knowledge_points WHERE id = ?', (kp_id,))
        kp = KnowledgePoint.from_row(row)
        kp_dict = kp.to_dict()
        kp_dict['tags'] = self._get_tags_for_knowledge(kp_id)
        self.op_service.log_operation('create', 'knowledge', kp_id, title,
            after_state={'id': kp_id, 'title': title, 'content': content, 'category_id': category_id})
        logger.info('创建知识点 id=%s title=%s', kp_id, title)
        return kp_dict

    def get_all(self, category_id=None, keyword=None, tag_id=None, tag_ids=None, page=1, page_size=50):
        conditions = []
        params = []

        if category_id:
            conditions.append('kp.category_id = ?')
            params.append(category_id)

        if keyword:
            conditions.append('(kp.title LIKE ? OR kp.content LIKE ?)')
            params.extend(['%' + keyword + '%', '%' + keyword + '%'])

        if tag_id:
            conditions.append('kp.id IN (SELECT knowledge_id FROM knowledge_tags WHERE tag_id = ?)')
            params.append(tag_id)

        if tag_ids:
            placeholders = ','.join(['?'] * len(tag_ids))
            conditions.append('kp.id IN (SELECT knowledge_id FROM knowledge_tags WHERE tag_id IN (' + placeholders + '))')
            params.extend(tag_ids)

        where_clause = ''
        if conditions:
            where_clause = 'WHERE ' + ' AND '.join(conditions)

        # Count total
        rows = self.db.execute_read(f'SELECT COUNT(*) FROM knowledge_points kp {where_clause}', params)
        total = rows[0][0]

        # Query with pagination
        offset = (page - 1) * page_size
        rows = self.db.execute_read(
            f'''SELECT kp.*, c.name as category_name
                FROM knowledge_points kp
                LEFT JOIN categories c ON kp.category_id = c.id
                {where_clause}
                ORDER BY kp.created_at DESC LIMIT ? OFFSET ?''',
            params + [page_size, offset]
        )

        items = []
        for row in rows:
            kp = KnowledgePoint.from_row(row).to_dict()
            kp['category_name'] = row['category_name'] or '未分类'
            kp['tags'] = self._get_tags_for_knowledge(row['id'])
            items.append(kp)
        return items, total

    def get_by_id(self, kp_id):
        row = self.db.execute_read_one(
            '''SELECT kp.*, c.name as category_name
               FROM knowledge_points kp
               LEFT JOIN categories c ON kp.category_id = c.id
               WHERE kp.id = ?''',
            (kp_id,)
        )
        if row:
            kp = KnowledgePoint.from_row(row).to_dict()
            kp['category_name'] = row['category_name'] or '未分类'
            kp['tags'] = self._get_tags_for_knowledge(kp_id)
            return kp
        return None

    def update(self, kp_id, title=None, content=None, category_id=None, tag_ids=None):
        # 查询 before_state
        old_row = self.db.execute_read_one('SELECT * FROM knowledge_points WHERE id = ?', (kp_id,))
        old_tag_ids = []
        if old_row:
            tag_rows = self.db.execute_read('SELECT tag_id FROM knowledge_tags WHERE knowledge_id = ?', (kp_id,))
            old_tag_ids = [r['tag_id'] for r in tag_rows]

        fields = []
        params = []
        if title is not None:
            fields.append('title = ?')
            params.append(title)
        if content is not None:
            fields.append('content = ?')
            params.append(content)
        if category_id is not None:
            fields.append('category_id = ?')
            params.append(category_id)
        if fields:
            fields.append('updated_at = CURRENT_TIMESTAMP')
            params.append(kp_id)
            self.db.execute_write(
                'UPDATE knowledge_points SET {} WHERE id = ?'.format(', '.join(fields)),
                params
            )
        self._set_tags(kp_id, tag_ids)
        row = self.db.execute_read_one('SELECT * FROM knowledge_points WHERE id = ?', (kp_id,))
        if row:
            kp = KnowledgePoint.from_row(row).to_dict()
            kp['tags'] = self._get_tags_for_knowledge(kp_id)
            if old_row:
                self.op_service.log_operation('update', 'knowledge', kp_id,
                    before_state={'id': kp_id, 'title': old_row['title'], 'content': old_row['content'],
                                  'category_id': old_row['category_id'], 'tag_ids': old_tag_ids},
                    after_state={'id': kp_id, 'title': title or old_row['title'],
                                 'content': content or old_row['content'],
                                 'category_id': category_id or old_row['category_id'],
                                 'tag_ids': tag_ids or old_tag_ids})
            logger.info('更新知识点 id=%s', kp_id)
            return kp
        return None

    def duplicate(self, kp_id):
        row = self.db.execute_read_one('SELECT * FROM knowledge_points WHERE id = ?', (kp_id,))
        if not row:
            return None
        new_title = row['title'] + '（副本）'
        cursor = self.db.execute_write(
            'INSERT INTO knowledge_points (title, content, category_id) VALUES (?, ?, ?)',
            (new_title, row['content'], row['category_id'])
        )
        new_id = cursor.lastrowid
        tag_rows = self.db.execute_read(
            'SELECT tag_id FROM knowledge_tags WHERE knowledge_id = ?',
            (kp_id,)
        )
        for tr in tag_rows:
            self.db.execute_write(
                'INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)',
                (new_id, tr['tag_id'])
            )
        new_row = self.db.execute_read_one('SELECT * FROM knowledge_points WHERE id = ?', (new_id,))
        kp = KnowledgePoint.from_row(new_row).to_dict()
        kp['tags'] = self._get_tags_for_knowledge(new_id)
        logger.info('复制知识点 id=%s -> id=%s title=%s', kp_id, new_id, new_title)
        return kp

    def delete(self, kp_id):
        old_row = self.db.execute_read_one('SELECT * FROM knowledge_points WHERE id = ?', (kp_id,))
        before = None
        if old_row:
            tag_rows = self.db.execute_read('SELECT tag_id FROM knowledge_tags WHERE knowledge_id = ?', (kp_id,))
            old_tag_ids = [r['tag_id'] for r in tag_rows]
            before = {
                'id': old_row['id'], 'title': old_row['title'],
                'content': old_row['content'], 'category_id': old_row['category_id'],
                'created_at': old_row['created_at'], 'updated_at': old_row['updated_at'],
                'tag_ids': old_tag_ids
            }
        cursor = self.db.execute_write('DELETE FROM knowledge_points WHERE id = ?', (kp_id,))
        affected = cursor.rowcount
        if affected > 0 and old_row:
            self.op_service.log_operation('delete', 'knowledge', kp_id,
                old_row['title'], before_state=before)
            logger.info('删除知识点 id=%s title=%s', kp_id, old_row['title'])
        return affected > 0

    def import_batch(self, items):
        success = 0
        failed = 0
        errors = []
        created_ids = []

        def do_import(cursor):
            nonlocal success, failed, errors, created_ids
            for i, item in enumerate(items):
                try:
                    title = item.get('title', '')
                    content = item.get('content', '')
                    category_id = item.get('category_id')
                    category_name = item.get('category')
                    tags = item.get('tags', [])

                    if not title:
                        failed += 1
                        errors.append({'index': i, 'error': 'title is required'})
                        continue

                    # 支持 category（名称）和 category_id（数字）两种方式
                    if category_id is None and category_name:
                        cursor.execute('SELECT id FROM categories WHERE name = ?', (category_name,))
                        cat_row = cursor.fetchone()
                        if cat_row:
                            category_id = cat_row['id']
                        else:
                            # 自动创建分类
                            cursor.execute('INSERT INTO categories (name, description) VALUES (?, ?)', (category_name, ''))
                            category_id = cursor.lastrowid

                    if not category_id:
                        failed += 1
                        errors.append({'index': i, 'error': 'category or category_id is required'})
                        continue

                    cursor.execute(
                        'INSERT INTO knowledge_points (title, content, category_id) VALUES (?, ?, ?)',
                        (title, content, category_id)
                    )
                    kp_id = cursor.lastrowid
                    created_ids.append(kp_id)
                    for tag_name in tags:
                        cursor.execute(
                            'INSERT OR IGNORE INTO tags (name) VALUES (?)',
                            (tag_name,)
                        )
                        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
                        tag_row = cursor.fetchone()
                        if tag_row:
                            cursor.execute(
                                'INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)',
                                (kp_id, tag_row['id'])
                            )
                    success += 1
                except Exception as e:
                    failed += 1
                    errors.append({'index': i, 'error': str(e)})

        self.db.execute_transaction(do_import)

        if created_ids:
            self.op_service.log_operation('import', 'knowledge', 0,
                '导入{}条'.format(len(created_ids)), affected_ids=created_ids)
            logger.info('导入知识点 %s 条，成功=%s 失败=%s', len(items), success, failed)
        return {'success': success, 'failed': failed, 'errors': errors}

    def export_data(self, ids, format='json', fields=None):
        placeholders = ','.join('?' * len(ids))
        rows = self.db.execute_read(
            f'''SELECT kp.*, c.name as category_name
                FROM knowledge_points kp
                LEFT JOIN categories c ON kp.category_id = c.id
                WHERE kp.id IN ({placeholders})
                ORDER BY kp.created_at DESC''',
            ids
        )

        items = []
        for row in rows:
            kp = KnowledgePoint.from_row(row).to_dict()
            kp['category_name'] = row['category_name'] or '未分类'
            kp['tags'] = self._get_tags_for_knowledge(row['id'])
            items.append(kp)

        if format == 'txt':
            lines = []
            for i, item in enumerate(items):
                if fields:
                    idx = i + 1
                    lines.append(f"--- 知识点 {idx} ---")
                    if fields.get('title'):
                        lines.append(f"标题: {item['title']}")
                    if fields.get('content'):
                        lines.append(f"内容: {item['content']}")
                    if fields.get('category'):
                        lines.append(f"分类: {item['category_name']}")
                    if fields.get('tags') and item.get('tags'):
                        tag_names = [t['name'] for t in item['tags']]
                        lines.append(f"标签: {', '.join(tag_names)}")
                    lines.append('')
                else:
                    lines.append(f"标题: {item['title']}")
                    lines.append(f"分类: {item['category_name']}")
                    if item.get('tags'):
                        tag_names = [t['name'] for t in item['tags']]
                        lines.append(f"标签: {', '.join(tag_names)}")
                    lines.append(f"内容:\n{item['content']}")
                    lines.append('')
                    lines.append('---')
                    lines.append('')
            return '\n'.join(lines)
        else:
            return json.dumps(items, ensure_ascii=False, indent=2)