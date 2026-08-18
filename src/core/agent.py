import os
import sys
from typing import List


class Agent:
    def __init__(self, name: str):
        self.name = name

    def perceive(self, environment: dict) -> None:
        # Implement perception logic here
        pass

    def reason(self, perception: dict) -> None:
        # Implement reasoning logic here
        pass

    def act(self, decision: dict) -> None:
        # Implement action logic here
        pass

    def learn(self, outcome: dict) -> None:
        # Implement learning logic here
        pass
