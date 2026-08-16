class OperationLog:
    def __init__(self, id, op_type, entity_type, entity_id, entity_name,
                 before_state, after_state, affected_ids, created_at):
        self.id = id
        self.op_type = op_type
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.before_state = before_state
        self.after_state = after_state
        self.affected_ids = affected_ids
        self.created_at = created_at

    def to_dict(self):
        return {
            'id': self.id, 'op_type': self.op_type,
            'entity_type': self.entity_type, 'entity_id': self.entity_id,
            'entity_name': self.entity_name,
            'before_state': self.before_state, 'after_state': self.after_state,
            'affected_ids': self.affected_ids, 'created_at': self.created_at
        }