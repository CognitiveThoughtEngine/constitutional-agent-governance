# OpenAI Agents SDK Integration Quickstart

**constitutional-agent** adds a WHY layer above the OpenAI Agents SDK. The pattern:
intercept tool calls before they execute. If `constitution.evaluate()` returns STOP or
FREEZE, raise an exception that the SDK treats as a tool failure — preventing execution.

## Install

```bash
pip install constitutional-agent openai-agents
```

## Minimal Example — Pre-tool-call constitutional guard

```python
import asyncio
from constitutional_agent import Constitution, SystemState

from agents import Agent, Runner, function_tool, RunContextWrapper

# Load governance config once at startup
constitution = Constitution.load("governance.yaml")


def get_runtime_context() -> dict:
    """
    Build the constitutional evaluation context from your runtime state.
    Replace with real metrics from your monitoring layer.
    """
    return {
        "hours_since_last_execution": 3,
        "failing_tests": 0,
        "runway_months": 9.0,
        "verification_pass_rate": 0.88,
        "lessons_learned_weekly": 2,
    }


@function_tool
def send_notification(user_id: str, message: str) -> str:
    """Send a notification to a user. Constitutional guard runs before this executes."""
    # Constitutional evaluation happens in the hook below —
    # if we reach this line, the constitution permitted execution.
    return f"Notification sent to {user_id}: {message[:40]}"


@function_tool
def delete_user_data(user_id: str) -> str:
    """Delete all data for a user. Irreversible — constitutional guard is strict here."""
    return f"Data deleted for {user_id}"


# --- Constitutional hook: runs before every tool call ---

class ConstitutionalRunHooks:
    """
    Hook into the OpenAI Agents SDK lifecycle.
    Raise an exception to treat the tool call as failed without executing it.
    """

    async def on_tool_call(
        self,
        context: RunContextWrapper,
        tool_name: str,
        tool_input: dict,
    ) -> None:
        """Called before each tool executes. Raise to block execution."""
        ctx = get_runtime_context()
        result = constitution.evaluate(ctx)

        if result.system_state == SystemState.STOP:
            raise RuntimeError(
                f"Constitutional STOP — all tool calls blocked. "
                f"Reason: {result.blocking_gate.reason}. "
                f"Human intervention required."
            )

        if result.system_state == SystemState.FREEZE:
            raise RuntimeError(
                f"Constitutional FREEZE — tool '{tool_name}' blocked. "
                f"Gate: {result.blocking_gate.gate} | {result.blocking_gate.reason}"
            )

        # THROTTLE: log but allow — caller can tighten this per tool
        if result.system_state == SystemState.THROTTLE:
            hold_names = [g.gate for g in result.hold_gates]
            print(f"[THROTTLE] Tool '{tool_name}' running under hold: {hold_names}")


# --- Agent wired with constitutional hook ---

async def main() -> None:
    agent = Agent(
        name="ConstitutionalAgent",
        instructions="You are a helpful assistant. Use tools only when necessary.",
        tools=[send_notification, delete_user_data],
    )

    hooks = ConstitutionalRunHooks()

    result = await Runner.run(
        agent,
        input="Send a welcome message to user-42.",
        hooks=hooks,
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
```

## STOP vs FREEZE — what the SDK sees

| Constitutional state | Exception raised | SDK behavior |
|----------------------|-----------------|--------------|
| `STOP` | `RuntimeError` — all tools blocked | Tool call marked failed; agent sees error |
| `FREEZE` | `RuntimeError` — specific gate blocked | Tool call marked failed; agent may retry |
| `THROTTLE` | None — warning logged | Tool executes; monitor hold_gates |
| `RUN` / `COMPOUND` | None | Tool executes normally |

## Which gates matter most for OpenAI Agents SDK

| Gate | Why it fires in Agents SDK flows |
|------|----------------------------------|
| **AutonomyGate** | Long-running agent loops without human checkpoints |
| **RiskGate** | Tool calls with external side-effects (delete, send, pay) |
| **ConstitutionalGate** | Self-modification or instruction override attempts |

## FRIA evidence for auditors

```python
from constitutional_agent import Constitution

constitution = Constitution.load("governance.yaml")
context = get_runtime_context()

# Generate EU AI Act Article 27 FRIA evidence
evidence = constitution.fria_evidence(context)
print(evidence.summary())
# → Structured output covering all 6 FRIA categories
```

## Further reading

- [CGST self-assessment (63/100)](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance)
- [EU AI Act FRIA — Article 27](../../README.md#eu-ai-act-article-27--fria-output-v040)
- [Fail-CLOSED principle](../../SECURITY.md)
- [governance.yaml reference](../../examples/)
