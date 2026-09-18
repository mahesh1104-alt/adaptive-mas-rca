from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

from app.agents.log_analysis_agent import LogAnalysisAgent
from app.agents.metrics_analysis_agent import MetricsAnalysisAgent
from app.agents.source_code_analysis_agent import SourceCodeAnalysisAgent
from app.trace_analysis_agent import TraceAnalysisAgent
from app.trace_preprocessing import summarize_trace
from app.ollama_adapter import ollama_llm
from app.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.validation_agent import ValidationAgent

class TraceLLMAdapter:
    def invoke(self, prompt):
        import ollama

        response = ollama.chat(
            model="llama3",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format="json",
        )

        return response["message"]["content"]

class GraphState(TypedDict, total=False):
    raw_inputs: dict[str, Any]
    agent_outputs: dict[str, dict[str, Any]]


def build_graph(
    log_llm=None,
    metrics_llm=None,
    source_llm=None,
    trace_llm=None,
):
    """
    Build the multi-agent RCA workflow.

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
        Source Code Analysis Agent
          |
          v
        Trace Analysis Agent
          |
          v
        END
    """

    if log_llm is None:
        log_llm = ollama_llm

    if metrics_llm is None:
        metrics_llm = ollama_llm

    if source_llm is None:
        source_llm = ollama_llm

    if trace_llm is None:
        trace_llm = TraceLLMAdapter()

    log_agent = LogAnalysisAgent(llm=log_llm)
    metrics_agent = MetricsAnalysisAgent(llm=metrics_llm)

    source_agent = SourceCodeAnalysisAgent(
        llm=source_llm
    )

    trace_agent = TraceAnalysisAgent(
        llm=trace_llm
    )
    knowledge_agent = KnowledgeRetrievalAgent()
    reasoning_agent = ReasoningAgent()
    validation_agent = ValidationAgent()

    builder = StateGraph(GraphState)

    # --------------------------------------------------
    # LOG ANALYSIS NODE
    # --------------------------------------------------

    def log_analysis_node(state: GraphState) -> dict[str, Any]:

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

    # --------------------------------------------------
    # METRICS ANALYSIS NODE
    # --------------------------------------------------

    def metrics_analysis_node(state: GraphState) -> dict[str, Any]:

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

    # --------------------------------------------------
    # SOURCE CODE ANALYSIS NODE
    # --------------------------------------------------

    def source_code_analysis_node(
        state: GraphState,
    ) -> dict[str, Any]:

        result = source_agent.run(
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

        outputs["source_code_analysis_agent"] = result

        return {
            "agent_outputs": outputs
        }

    # --------------------------------------------------
    # TRACE ANALYSIS NODE
    # --------------------------------------------------

    def trace_analysis_node(
        state: GraphState,
    ) -> dict[str, Any]:

        raw_inputs = state.get(
            "raw_inputs",
            {},
        )

        trace_data = raw_inputs.get(
            "trace",
        )

        if trace_data is None:
            raise ValueError(
                "raw_inputs.trace is required"
            )

        trace_summary = summarize_trace(
            trace_data
        )

        result = trace_agent.analyze(
            trace_summary
        )

        outputs = dict(
            state.get(
                "agent_outputs",
                {},
            )
        )

        outputs["trace_analysis_agent"] = (
            result.model_dump()
            if hasattr(result, "model_dump")
            else result
        )

        return {
            "agent_outputs": outputs
        }

    def knowledge_retrieval_node(state: GraphState) -> dict[str, Any]:
        result = knowledge_agent.run({
            "raw_inputs": state.get("raw_inputs", {})
        })

        outputs = dict(state.get("agent_outputs", {}))
        outputs["knowledge_retrieval_agent"] = (
            result.model_dump() if hasattr(result, "model_dump") else result
        )

        return {"agent_outputs": outputs}

    def reasoning_node(state: GraphState) -> dict[str, Any]:
        result = reasoning_agent.run({
            "raw_inputs": state.get("raw_inputs", {}),
            "agent_outputs": state.get("agent_outputs", {}),
        })

        outputs = dict(state.get("agent_outputs", {}))
        outputs["reasoning_agent"] = (
            result.model_dump()
            if hasattr(result, "model_dump")
            else result
        )

        return {
            "agent_outputs": outputs
        }

    def validation_node(state: GraphState) -> dict[str, Any]:
        result = validation_agent.run({
            "raw_inputs": state.get("raw_inputs", {}),
            "agent_outputs": state.get("agent_outputs", {}),
        })

        outputs = dict(state.get("agent_outputs", {}))
        outputs["validation_agent"] = (
            result.model_dump()
            if hasattr(result, "model_dump")
            else result
        )

        return {
            "agent_outputs": outputs
        }

    # --------------------------------------------------
    # REGISTER NODES
    # --------------------------------------------------

    builder.add_node(
        "log_analysis_agent",
        log_analysis_node,
    )

    builder.add_node(
        "metrics_analysis_agent",
        metrics_analysis_node,
    )

    builder.add_node(
        "source_code_analysis_agent",
        source_code_analysis_node,
    )

    builder.add_node(
        "trace_analysis_agent",
        trace_analysis_node,
    )

    builder.add_node(
        "knowledge_retrieval_agent",
        knowledge_retrieval_node
    )

    builder.add_node(
        "reasoning_agent",
        reasoning_node
    )

    builder.add_node(
        "validation_agent",
        validation_node
    )

    # --------------------------------------------------
    # CONNECT WORKFLOW
    # --------------------------------------------------

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
        "source_code_analysis_agent",
    )

    builder.add_edge(
        "source_code_analysis_agent",
        "trace_analysis_agent",
    )

    builder.add_edge(
        "trace_analysis_agent",
        "knowledge_retrieval_agent"
    )

    builder.add_edge(
        "knowledge_retrieval_agent",
        "reasoning_agent"
    )

    builder.add_edge(
        "reasoning_agent",
        "validation_agent"
    )

    builder.add_edge(
        "validation_agent",
        END
    )

    return builder.compile()


graph = build_graph()