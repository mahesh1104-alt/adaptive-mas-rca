from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

from app.agents.log_analysis_agent import LogAnalysisAgent
from app.agents.metrics_analysis_agent import MetricsAnalysisAgent
from app.ollama_adapter import ollama_llm


class GraphState(TypedDict, total=False):
    raw_inputs: dict[str, Any]
    agent_outputs: dict[str, dict[str, Any]]


def build_graph(
    log_llm=None,
    metrics_llm=None,
):
    """
    Build the multi-agent RCA workflow.

    If an LLM is not explicitly supplied, Ollama is used.
    This keeps fake-LLM injection available for unit tests.

    Flow:
        START
          |
          v
        Log Analysis Agent
          |
          v
        Metrics Analysis Agent
          |
          v
        END
    """

    if log_llm is None:
        log_llm = ollama_llm

    if metrics_llm is None:
        metrics_llm = ollama_llm

    log_agent = LogAnalysisAgent(
        llm=log_llm
    )

    metrics_agent = MetricsAnalysisAgent(
        llm=metrics_llm
    )

    builder = StateGraph(GraphState)

    def log_analysis_node(
        state: GraphState,
    ) -> dict[str, Any]:

        result = log_agent.run(
            {
                "raw_inputs": state.get(
                    "raw_inputs",
                    {},
                )
            }
        )

        outputs = dict(
            state.get(
                "agent_outputs",
                {},
            )
        )

        outputs["log_analysis_agent"] = result

        return {
            "agent_outputs": outputs
        }

    def metrics_analysis_node(
        state: GraphState,
    ) -> dict[str, Any]:

        result = metrics_agent.run(
            {
                "raw_inputs": state.get(
                    "raw_inputs",
                    {},
                )
            }
        )

        outputs = dict(
            state.get(
                "agent_outputs",
                {},
            )
        )

        outputs["metrics_analysis_agent"] = result

        return {
            "agent_outputs": outputs
        }

    builder.add_node(
        "log_analysis_agent",
        log_analysis_node,
    )

    builder.add_node(
        "metrics_analysis_agent",
        metrics_analysis_node,
    )

    builder.add_edge(
        START,
        "log_analysis_agent",
    )

    builder.add_edge(
        "log_analysis_agent",
        "metrics_analysis_agent",
    )

    builder.add_edge(
        "metrics_analysis_agent",
        END,
    )

    return builder.compile()


graph = build_graph()
