class Category:
    def __init__(self, id=None, name='', description='', created_at=None):
        self.id = id
        self.name = name
        self.description = description
        self.created_at = created_at

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            created_at=row['created_at']
        )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at
        }