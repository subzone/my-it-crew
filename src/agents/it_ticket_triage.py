# Implement the reasoning module using LLM for IT ticket triage decision making.

class ITTicketTriageAgent(BaseAgent):
    def __init__(self, agent_id: str, persona: str, model: str | None = None):
        super().__init__(agent_id, persona, model)
        self.settings = Settings()
        self.model = model or self.settings.default_model
        self.state = AgentState(agent_id=agent_id)
        self.client = AsyncOpenAI(
            base_url=self.settings.litellm_api_base,
            api_key=self.settings.litellm_api_key,
        )
        self.tools: dict[str, Any] = {}
        self.skills: dict[str, SkillPlugin] = {}
        self._skill_tool_names: dict[str, list[str]] = {}
        self.max_iterations = 15
        self.log = logger.bind(agent=agent_id)
        self._status: AgentStatus = AgentStatus.STOPPED
        self._started_at: datetime | None = None

    # ...