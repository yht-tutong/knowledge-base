import sqlite3
import os
import threading


class Database:
    _instance = None
    _lock = threading.Lock()
    _write_lock = threading.Lock()
    _connection = None
    _db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge.db')

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def _get_connection(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self._db_path, timeout=5, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 5000")
        else:
            try:
                self._connection.execute("SELECT 1")
            except sqlite3.ProgrammingError:
                self._connection = sqlite3.connect(self._db_path, timeout=5, check_same_thread=False)
                self._connection.row_factory = sqlite3.Row
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA busy_timeout = 5000")
        return self._connection

    def execute_write(self, sql, params=None):
        """执行写操作（INSERT/UPDATE/DELETE），自动获取写锁并提交"""
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor

    def execute_read(self, sql, params=None):
        """执行只读查询，返回所有行（每次获取新连接，避免多线程问题）"""
        conn = sqlite3.connect(self._db_path, timeout=5, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        result = cursor.fetchall()
        conn.close()
        return result

    def execute_read_one(self, sql, params=None):
        """执行只读查询，返回单行（每次获取新连接，避免多线程问题）"""
        conn = sqlite3.connect(self._db_path, timeout=5, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        result = cursor.fetchone()
        conn.close()
        return result

    def execute_transaction(self, callback):
        """在写锁保护下执行事务回调。
        callback 接收 cursor 参数，在其中执行所有数据库操作。
        事务自动提交，异常时回滚。返回 callback 的返回值。
        """
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                result = callback(cursor)
                conn.commit()
                return result
            except Exception:
                conn.rollback()
                raise

    def init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 预置高中学科分类
        default_categories = [
            ('语文', ''),
            ('数学', ''),
            ('英语', ''),
            ('物理', ''),
            ('化学', ''),
            ('生物', ''),
            ('政治', ''),
            ('历史', ''),
            ('地理', ''),
            ('技术', ''),
            ('未分类', ''),
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)',
            default_categories
        )
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                category_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                shape TEXT NOT NULL DEFAULT 'ellipse',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                UNIQUE(knowledge_id, tag_id),
                FOREIGN KEY (knowledge_id) REFERENCES knowledge_points(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                entity_name TEXT DEFAULT '',
                before_state TEXT DEFAULT '{}',
                after_state TEXT DEFAULT '{}',
                affected_ids TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 迁移：为 tags 表添加 color 列
        try:
            cursor.execute("ALTER TABLE tags ADD COLUMN color TEXT DEFAULT ''")
        except Exception:
            pass

        conn.commit()

    def close(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def checkpoint(self):
        if self._connection:
            self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")