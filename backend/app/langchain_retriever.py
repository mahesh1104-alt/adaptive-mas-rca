from pydantic import field_validator
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from .hybrid_retrieval import retrieval
from .retrieval_cache import cached_retrieval


class HybridLangChainRetriever(BaseRetriever):
    """
    LangChain-compatible retriever wrapping the project's
    hybrid ChromaDB + Neo4j retrieval pipeline.
    """

    top_k: int = 10
    score_threshold: float = 0.0

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        if value < 1:
            raise ValueError("top_k must be at least 1")
        return value

    @field_validator("score_threshold")
    @classmethod
    def validate_score_threshold(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                "score_threshold must be between 0.0 and 1.0"
            )
        return value

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager,
    ) -> list[Document]:
        results = cached_retrieval(
            query=query,
            top_k=self.top_k,
            retrieval_function=retrieval,
        )

        filtered_results = [
            result
            for result in results
            if result.get("relevance_score", 0.0)
            >= self.score_threshold
        ]

        documents = []

        for result in filtered_results:
            document_text = result.get("document", "")

            graph_evidence = result.get(
                "graph_evidence",
                [],
            )

            if graph_evidence:
                graph_lines = []

                for evidence in graph_evidence:
                    graph_lines.append(
                        "Graph evidence: "
                        f"service={evidence.get('service', '')}; "
                        f"root_cause={evidence.get('root_cause', '')}; "
                        f"hops={evidence.get('hop_count', '')}"
                    )

                graph_text = "\n".join(graph_lines)

                if document_text:
                    document_text = (
                        f"{document_text}\n\n"
                        f"{graph_text}"
                    )
                else:
                    document_text = graph_text

            metadata = {
                "incident_id": result.get("incident_id"),
                "service": result.get("service"),
                "title": result.get("title"),
                "vector_distance": result.get("vector_distance"),
                "vector_score": result.get("vector_score"),
                "graph_score": result.get("graph_score"),
                "relevance_score": result.get(
                    "relevance_score"
                ),
                "graph_evidence": graph_evidence,
            }

            documents.append(
                Document(
                    page_content=document_text,
                    metadata=metadata,
                )
            )

        return documents