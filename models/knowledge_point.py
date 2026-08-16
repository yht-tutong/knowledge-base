class KnowledgePoint:
    def __init__(self, id=None, title='', content='', category_id=None, created_at=None, updated_at=None):
        self.id = id
        self.title = title
        self.content = content
        self.category_id = category_id
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            title=row['title'],
            content=row['content'],
            category_id=row['category_id'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'category_id': self.category_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }