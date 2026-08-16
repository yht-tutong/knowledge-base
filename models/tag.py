class Tag:
    def __init__(self, id=None, name='', shape='ellipse', color='', created_at=None):
        self.id = id
        self.name = name
        self.shape = shape
        self.color = color
        self.created_at = created_at

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=row['id'],
            name=row['name'],
            shape=row['shape'],
            color=row['color'] if 'color' in row.keys() else '',
            created_at=row['created_at']
        )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'shape': self.shape,
            'color': self.color,
            'created_at': self.created_at
        }