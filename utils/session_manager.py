from datetime import datetime
from config import DEFAULT_MODEL

class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.history = []
        self.current_model = DEFAULT_MODEL
        self.created_at = datetime.now()
        self.message_count = 0
        self.last_activity = datetime.now()

user_sessions = {}