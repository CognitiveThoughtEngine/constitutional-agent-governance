# CrewAI Integration Quickstart

**constitutional-agent** adds a WHY layer above CrewAI's WHO (agents) and HOW (tasks).
The pattern: check constitution before each agent action. If RiskGate FAILs, refuse the action.

## Install

```bash
pip install constitutional-agent crewai
```

## Minimal Example — Constitutional check before agent step

```python
from constitutional_agent import Constitution, SystemState, GateState
from crewai import Agent, Task, Crew

# Load governance config once at startup
constitution = Constitution.load("governance.yaml")


def constitutional_step_guard(agent_context: dict) -> None:
    """
    Call before any CrewAI agent step that takes an external action.
    Raises RuntimeError if constitution blocks. Caller should catch and refuse.
    """
    result = constitution.evaluate(agent_context)

    if result.system_state in (SystemState.FREEZE, SystemState.STOP):
        gate = result.blocking_gate
        raise RuntimeError(
            f"Constitutional FREEZE — action refused. "
            f"Gate: {gate.gate} | Reason: {gate.reason}"
        )

    # Surface throttle warnings without hard blocking
    if result.system_state == SystemState.THROTTLE:
        hold_names = [g.gate for g in result.hold_gates]
        print(f"[THROTTLE] Proceeding with caution. Hold gates: {hold_names}")


# --- Example: Research agent with constitutional guard ---

def run_research_task(topic: str) -> str:
    """Run a CrewAI research task only if constitution permits."""
    context = {
        "hours_since_last_execution": 1,
        "failing_tests": 0,
        "runway_months": 7.0,
        "verification_pass_rate": 0.85,
    }

    try:
        constitutional_step_guard(context)
    except RuntimeError as e:
        return f"REFUSED: {e}"

    # Constitution passed — execute CrewAI task
    researcher = Agent(
        role="Senior Researcher",
        goal=f"Research {topic} thoroughly",
        backstory="Expert researcher with domain knowledge.",
        verbose=False,
    )

    task = Task(
        description=f"Research the topic: {topic}. Provide a 3-paragraph summary.",
        agent=researcher,
        expected_output="A concise 3-paragraph research summary.",
    )

    crew = Crew(agents=[researcher], tasks=[task], verbose=False)
    result = crew.kickoff()
    return str(result)
```

## RiskGate mapping for CrewAI actions

```python
from constitutional_agent import Constitution, GateState

constitution = Constitution.load("governance.yaml")

RISKY_ACTIONS = {"send_email", "make_payment", "delete_record", "publish_post"}

def should_allow_tool_call(tool_name: str, context: dict) -> tuple[bool, str]:
    """Returns (allowed, reason). Stricter check for irreversible actions."""
    result = constitution.evaluate(context)

    # Any FREEZE blocks everything
    if result.system_state.value in ("FREEZE", "STOP"):
        return False, f"System FREEZE: {result.blocking_gate.reason}"

    # For risky actions, also block on RiskGate HOLD (not just FAIL)
    if tool_name in RISKY_ACTIONS:
        for gate in result.hold_gates:
            if gate.gate == "RiskGate":
                return False, f"RiskGate HOLD on irreversible action '{tool_name}': {gate.reason}"

    return True, "Permitted"
```

## Which gates matter most for CrewAI

| Gate | Why it fires in CrewAI flows |
|------|------------------------------|
| **RiskGate** | Agent about to call a tool with external side-effects |
| **GovernanceGate** | Multi-agent crew running without a ratified mandate |
| **EpistemicGate** | Agent acting on retrieved context with low verification rate |

## Further reading

- [CGST self-assessment (63/100)](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance)
- [Fail-CLOSED principle](../../SECURITY.md)
- [governance.yaml reference](../../examples/)
