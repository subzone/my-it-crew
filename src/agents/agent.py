# Agent class definition

class Agent:
    def __init__(self, name, role):
        self.name = name
        self.role = role

    def __str__(self):
        return f"Agent {self.name} - {self.role}"