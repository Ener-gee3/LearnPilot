import json
import os
from datetime import datetime

HISTORY_FILE = "history.json"

class HistoryService:
    @staticmethod
    def save_session(mode, topic, response):
        session_data = {
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "topic": topic,
            "response": response
        }
        
        # Load existing history or start new list
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                try:
                    history = json.load(f)
                except json.JSONDecodeError:
                    history = []
        else:
            history = []
            
        history.append(session_data)
        
        # Save back to file
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
            
    @staticmethod
    def get_history():
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        return []
