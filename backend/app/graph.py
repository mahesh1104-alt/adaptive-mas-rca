from __future__ import annotations

import operator
import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
from app.agents.log_analysis_agent import LogAnalysisAgent
from app.agents.metrics_analysis_agent import MetricsAnalysisAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.source_code_analysis_agent import SourceCodeAnalysisAgent
from app.agents.validation_agent import ValidationAgent
from app.ollama_adapter import ollama_llm
from app.trace_analysis_agent import TraceAnalysisAgent
from app.trace_preprocessing import preprocess_trace
from app.diagnosis_events import publish_event
from app.agent_weighting import calculate_agent_trust_weights
from app.dependencies import SessionLocal

logger = logging.getLogger(__name__)

class TraceLLMAdapter:
    def invoke(self, prompt: str):
        import ollama

        response = ollama.chat(
            model="llama3:latest",
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"]


class GraphState(TypedDict, total=False):
    job_id: str
    raw_inputs: dict[str, Any]

    # Parallel branches return only their own dictionary entry.
    # operator.or_ safely merges those entries during fan-in.
    agent_outputs: Annotated[
        dict[str, dict[str, Any]],
        operator.or_,
    ]


def build_graph(
    log_llm=None,
    metrics_llm=None,
    source_llm=None,
    trace_llm=None,
):
    log_agent = LogAnalysisAgent(llm=log_llm or ollama_llm)
    metrics_agent = MetricsAnalysisAgent(llm=metrics_llm or ollama_llm)
    source_agent = SourceCodeAnalysisAgent(llm=source_llm or ollama_llm)
    trace_agent = TraceAnalysisAgent(llm=trace_llm or TraceLLMAdapter())

    knowledge_agent = KnowledgeRetrievalAgent()
    reasoning_agent = ReasoningAgent(llm=ollama_llm)
    validation_agent = ValidationAgent()

    def fallback_output(agent_name: str, error: Exception) -> dict[str, Any]:
        logger.exception(
            "%s failed during RCA graph execution: %s",
            agent_name,
            error,
        )

        return {
            "agent": agent_name,
            "status": "failed",
            "summary": "Insufficient data because this agent failed during execution.",
            "findings": [],
            "evidence": [],
            "hypotheses": [],
            "confidence": 0.0,
            "metadata": {
                "error": str(error),
                "requires_human_review": True,
                "fallback": True,
            },
        }

    
    def log_node(state: GraphState):
        job_id = state.get("job_id")

        try:
            result = log_agent.run(
                {"raw_inputs": state.get("raw_inputs", {})}
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="log_analysis_agent",
                status="completed",
                confidence=result.get("confidence", 0.0)
                if isinstance(result, dict)
                else 0.0,
                summary=(
                    result.get("summary")
                    if isinstance(result, dict)
                    else None
                ),
            )

            return {
                "agent_outputs": {
                    "log_analysis_agent": result
                }
            }

        except Exception as error:
            fallback = fallback_output(
                "log_analysis_agent",
                error,
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="log_analysis_agent",
                status="failed",
                error=str(error),
            )

            return {
                "agent_outputs": {
                    "log_analysis_agent": fallback
                }
            }

    def metrics_node(state: GraphState):
        job_id = state.get("job_id")

        try:
            result = metrics_agent.run(
                {"raw_inputs": state.get("raw_inputs", {})}
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="metrics_analysis_agent",
                status="completed",
                confidence=result.get("confidence", 0.0)
                if isinstance(result, dict)
                else 0.0,
                summary=(
                    result.get("summary")
                    if isinstance(result, dict)
                    else result.get("hypothesis")
                    if isinstance(result, dict)
                    else None
                ),
            )

            return {
                "agent_outputs": {
                    "metrics_analysis_agent": result
                }
            }

        except Exception as error:
            fallback = fallback_output(
                "metrics_analysis_agent",
                error,
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="metrics_analysis_agent",
                status="failed",
                error=str(error),
            )

            return {
                "agent_outputs": {
                    "metrics_analysis_agent": fallback
                }
            }

    def source_node(state: GraphState):
        job_id = state.get("job_id")

        try:
            result = source_agent.run(
                {"raw_inputs": state.get("raw_inputs", {})}
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="source_code_analysis_agent",
                status="completed",
                confidence=result.get("confidence", 0.0)
                if isinstance(result, dict)
                else 0.0,
                summary=(
                    result.get("summary")
                    if isinstance(result, dict)
                    else result.get("explanation")
                    if isinstance(result, dict)
                    else None
                ),
            )

            return {
                "agent_outputs": {
                    "source_code_analysis_agent": result
                }
            }

        except Exception as error:
            fallback = fallback_output(
                "source_code_analysis_agent",
                error,
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="source_code_analysis_agent",
                status="failed",
                error=str(error),
            )

            return {
                "agent_outputs": {
                    "source_code_analysis_agent": fallback
                }
            }

    def trace_node(state: GraphState):
        job_id = state.get("job_id")

        try:
            raw_inputs = state.get("raw_inputs", {})
            trace_input = raw_inputs.get("trace")

            if trace_input is None:
                raise ValueError(
                    "Trace input is required for Trace Analysis Agent."
                )

            trace_summary = preprocess_trace(trace_input)
            result = trace_agent.analyze(trace_summary)

            result_dict = result.model_dump()

            publish_event(
                job_id,
                "agent_completed",
                agent="trace_analysis_agent",
                status="completed",
                confidence=result_dict.get(
                    "confidence",
                    0.0,
                ),
                summary=result_dict.get("summary"),
            )

            return {
                "agent_outputs": {
                    "trace_analysis_agent": result_dict
                }
            }

        except Exception as error:
            fallback = fallback_output(
                "trace_analysis_agent",
                error,
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="trace_analysis_agent",
                status="failed",
                error=str(error),
            )

            return {
                "agent_outputs": {
                    "trace_analysis_agent": fallback
                }
            }
    def knowledge_node(state: GraphState):
        job_id = state.get("job_id")

        try:
            result = knowledge_agent.run(
                {"raw_inputs": state.get("raw_inputs", {})}
            )

            result_dict = result.model_dump()

            publish_event(
                job_id,
                "agent_completed",
                agent="knowledge_retrieval_agent",
                status="completed",
                confidence=result_dict.get(
                    "confidence",
                    0.0,
                ),
                summary=result_dict.get("summary"),
            )

            return {
                "agent_outputs": {
                    "knowledge_retrieval_agent": result_dict
                }
            }

        except Exception as error:
            fallback = fallback_output(
                "knowledge_retrieval_agent",
                error,
            )

            publish_event(
                job_id,
                "agent_completed",
                agent="knowledge_retrieval_agent",
                status="failed",
                error=str(error),
            )

            return {
                "agent_outputs": {
                    "knowledge_retrieval_agent": fallback
                }
            }

    def reasoning_node(state: GraphState):
        job_id = state.get("job_id")

        try:
            raw_inputs = state.get("raw_inputs", {})
            agent_outputs = state.get("agent_outputs", {})

            db = SessionLocal()

            try:
                agent_weights = calculate_agent_trust_weights(db)
            finally:
                db.close()

            state["agent_weights"] = agent_weights

            result = reasoning_agent.run(
                {
                    "raw_inputs": raw_inputs,
                    "agent_outputs": agent_outputs,
                    "agent_weights": agent_weights,
                }
            )

            result_dict = result.model_dump()

            publish_event(
                job_id,
                "agent_completed",
                agent="reasoning_agent",
                status="completed",
                confidence=result_dict.get(
                    "confidence",
                    0.0,
                ),
                summary=result_dict.get("summary"),
            )

            return {
                "agent_outputs": {
                    "reasoning_agent": result_dict
                }
            }

        except Exception as error:
            fallback = fallback_output(
                "reasoning_agent",
                error,
            )

            fallback["metadata"]["final_report"] = {
                "root_cause": None,
                "explanation": (
                    "Reasoning Agent failed. "
                    "A complete root-cause determination could not be produced."
                ),
                "confidence": 0.0,
                "supporting_evidence": [],
                "alternative_hypotheses": [],
                "contributing_agents": [],
                "recommended_actions": [],
                "ranked_root_causes": [],
                "requires_human_review": True,
            }

            publish_event(
                job_id,
                "agent_completed",
                agent="reasoning_agent",
                status="failed",
                error=str(error),
            )

            return {
                "agent_outputs": {
                    "reasoning_agent": fallback
                }
            }
    def validation_node(state: GraphState):
        job_id = state.get("job_id")

        try:
            raw_inputs = state.get("raw_inputs", {})
            agent_outputs = state.get("agent_outputs", {})

            result = validation_agent.run(
                {
                    "raw_inputs": raw_inputs,
                    "agent_outputs": agent_outputs,
                }
            )

            result_dict = result.model_dump()

            publish_event(
                job_id,
                "agent_completed",
                agent="validation_agent",
                status="completed",
                confidence=result_dict.get(
                    "confidence",
                    0.0,
                ),
                summary=result_dict.get("summary"),
            )

            return {
                "agent_outputs": {
                    "validation_agent": result_dict
                }
            }

        except Exception as error:
            fallback = fallback_output(
                "validation_agent",
                error,
            )

            fallback["metadata"]["validation"] = {
                "validated": False,
                "requires_human_review": True,
                "reason": (
                    "Validation Agent failed, so the RCA result "
                    "requires human review."
                ),
            }

            publish_event(
                job_id,
                "agent_completed",
                agent="validation_agent",
                status="failed",
                error=str(error),
            )

            return {
                "agent_outputs": {
                    "validation_agent": fallback
                }
            }

    workflow = StateGraph(GraphState)

    workflow.add_node("log_analysis", log_node)
    workflow.add_node("metrics_analysis", metrics_node)
    workflow.add_node("source_code_analysis", source_node)
    workflow.add_node("trace_analysis", trace_node)
    workflow.add_node("knowledge_retrieval", knowledge_node)
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("validation", validation_node)

    # ---------------------------------------------------------
    # PARALLEL FAN-OUT
    # ---------------------------------------------------------
    workflow.add_edge(START, "log_analysis")
    workflow.add_edge(START, "metrics_analysis")
    workflow.add_edge(START, "source_code_analysis")
    workflow.add_edge(START, "trace_analysis")

    # ---------------------------------------------------------
    # FAN-IN
    #
    # Knowledge Retrieval starts only after all four
    # specialized analysis branches complete.
    # ---------------------------------------------------------
    workflow.add_edge("log_analysis", "knowledge_retrieval")
    workflow.add_edge("metrics_analysis", "knowledge_retrieval")
    workflow.add_edge("source_code_analysis", "knowledge_retrieval")
    workflow.add_edge("trace_analysis", "knowledge_retrieval")

    # ---------------------------------------------------------
    # REASONING -> VALIDATION -> END
    # ---------------------------------------------------------
    workflow.add_edge("knowledge_retrieval", "reasoning")
    workflow.add_edge("reasoning", "validation")
    workflow.add_edge("validation", END)

    return workflow.compile()


graph = build_graph()
