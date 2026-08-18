import os

class ReasoningModule:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        
    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
