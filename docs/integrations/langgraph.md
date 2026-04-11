# LangGraph Integration Quickstart

**constitutional-agent** sits above LangGraph as a WHY layer: before any node executes,
evaluate the constitutional context. If the system is in FREEZE, skip the node entirely.

## Install

```bash
pip install constitutional-agent langgraph
```

## Minimal Example — Guard a "send email" node

```python
from constitutional_agent import Constitution, SystemState
from langgraph.graph import StateGraph, END
from typing import TypedDict

# Load governance config once at startup
constitution = Constitution.load("governance.yaml")


class AgentState(TypedDict):
    user_id: str
    email_body: str
    sent: bool


def send_email_node(state: AgentState) -> AgentState:
    """Node that sends an outbound email — guarded by constitutional evaluation."""
    context = {
        "hours_since_last_execution": 2,
        "failing_tests": 0,
        "runway_months": 8.5,
        "lessons_learned_weekly": 1,
    }

    result = constitution.evaluate(context)

    if result.system_state in (SystemState.FREEZE, SystemState.STOP):
        # Hard block — do not send. Log the reason.
        print(f"BLOCKED by {result.blocking_gate.gate}: {result.blocking_gate.reason}")
        return {**state, "sent": False}

    if result.system_state == SystemState.THROTTLE:
        # Soft hold — log and skip non-critical sends
        print(f"THROTTLE — skipping non-critical email: {result.summary}")
        return {**state, "sent": False}

    # COMPOUND or RUN — proceed
    _actually_send_email(state["user_id"], state["email_body"])
    return {**state, "sent": True}


def _actually_send_email(user_id: str, body: str) -> None:
    print(f"Sending email to {user_id}: {body[:40]}...")


# Wire the graph
graph = StateGraph(AgentState)
graph.add_node("send_email", send_email_node)
graph.set_entry_point("send_email")
graph.add_edge("send_email", END)
app = graph.compile()
```

## Which gates matter most for LangGraph

| Gate | Why it fires in LangGraph flows |
|------|--------------------------------|
| **EpistemicGate** | Node making decisions on stale or low-confidence data |
| **RiskGate** | Node about to take an irreversible external action (send, pay, delete) |
| **AutonomyGate** | Multi-step chains running without human checkpoints |

## Pattern: Reusable node wrapper

```python
from functools import wraps
from constitutional_agent import Constitution, SystemState

constitution = Constitution.load("governance.yaml")

def constitutional_node(context_fn):
    """Decorator — evaluates constitution before running the wrapped node."""
    def decorator(node_fn):
        @wraps(node_fn)
        def wrapper(state):
            ctx = context_fn(state) if callable(context_fn) else context_fn
            result = constitution.evaluate(ctx)
            if result.system_state in (SystemState.FREEZE, SystemState.STOP):
                raise RuntimeError(f"Constitutional FREEZE: {result.blocking_gate.reason}")
            return node_fn(state)
        return wrapper
    return decorator
```

## Further reading

- [CGST self-assessment (63/100)](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance)
- [Gate threshold calibration](../../CHANGELOG.md)
- [governance.yaml reference](../../examples/)
