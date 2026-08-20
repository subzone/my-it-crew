import pytest
from src.agents.base import BaseAgent

@pytest.fixture
def agent():
    return BaseAgent(agent_id='test', persona='test')

def test_perceive(agent):
    # Test perceive method
    pass
def test_reflect(agent):
    # Test reflect method
    pass