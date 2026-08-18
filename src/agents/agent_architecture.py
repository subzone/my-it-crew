class AgentArchitecture:
    def __init__(self):
        self.perception = Perception()
        self.reasoning = Reasoning()
        self.action = Action()
        self.learning = Learning()