import unittest
from src.pilot_phases import PilotPhase, PilotProgram

class TestPilotPhases(unittest.TestCase):
    def test_pilot_phase(self):
        phase = PilotPhase('Setup', ['Objective 1', 'Objective 2'], ['Criteria 1', 'Criteria 2'], ['Criteria 3', 'Criteria 4'])
        self.assertEqual(phase.name, 'Setup')
        self.assertEqual(phase.objectives, ['Objective 1', 'Objective 2'])
        self.assertEqual(phase.entry_criteria, ['Criteria 1', 'Criteria 2'])
        self.assertEqual(phase.exit_criteria, ['Criteria 3', 'Criteria 4'])
