import pytest
from src.agents.it_ticket_triage import ITTicketTriageAgent

@pytest.fixture
def agent():
    return ITTicketTriageAgent(
        agent_id="test-it-ticket-triage",
        persona="Test IT Ticket Triage Agent",
    )

def test_perceive(agent):
    # Test perceive method
    events = agent.perceive()
    assert len(events) > 0

def test_reflect(agent):
    # Test reflect method
    result = agent.reflect({"status": "completed"})
    assert result == {"status": "completed"}