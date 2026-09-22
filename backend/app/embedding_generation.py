from sentence_transformers import SentenceTransformer


# ============================================================
# EMBEDDING MODEL CONFIGURATION
# ============================================================

MODEL_NAME = "all-MiniLM-L6-v2"

# Load the model once when this module is imported
embedding_model = SentenceTransformer(MODEL_NAME)

# Get embedding dimension
EMBEDDING_DIMENSION = embedding_model.get_embedding_dimension()


# ============================================================
# SINGLE TEXT EMBEDDING
# ============================================================

def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector for a single text.

    Args:
        text: Input text to embed.

    Returns:
        List of floating-point embedding values.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    text = text.strip()

    if not text:
        raise ValueError("text cannot be empty")

    embedding = embedding_model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return embedding.tolist()


# ============================================================
# FEATURE BUNDLE -> TEXT
# ============================================================

def feature_bundle_to_text(feature_bundle: dict) -> str:
    """
    Convert a Task-30 feature bundle into a text document
    suitable for embedding generation.

    The feature bundle may contain:
        - logs
        - metrics
        - traces
        - source
    """

    if not isinstance(feature_bundle, dict):
        raise TypeError(
            "feature_bundle must be a dictionary"
        )

    features = feature_bundle.get(
        "features",
        {}
    )

    if not isinstance(features, dict):
        raise ValueError(
            "feature_bundle['features'] must be a dictionary"
        )

    text_parts = []

    # --------------------------------------------------------
    # INCIDENT
    # --------------------------------------------------------

    incident_id = feature_bundle.get(
        "incident_id",
        "UNKNOWN"
    )

    text_parts.append(
        f"INCIDENT ID: {incident_id}"
    )

    # --------------------------------------------------------
    # LOGS
    # --------------------------------------------------------

    logs = features.get(
        "logs",
        []
    )

    if logs:
        text_parts.append("LOGS:")

        for log in logs:

            if not isinstance(log, dict):
                continue

            level = log.get(
                "level",
                "INFO"
            )

            message = log.get(
                "template",
                log.get(
                    "message",
                    ""
                )
            )

            if message:
                text_parts.append(
                    f"{level}: {message}"
                )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    metrics = features.get(
        "metrics",
        []
    )

    if metrics:
        text_parts.append("METRICS:")

        for metric in metrics:

            if not isinstance(metric, dict):
                continue

            metric_name = metric.get(
                "metric",
                metric.get(
                    "name",
                    "unknown"
                )
            )

            value = metric.get(
                "value",
                ""
            )

            unit = metric.get(
                "unit",
                ""
            )

            anomaly = metric.get(
                "anomaly",
                False
            )

            text_parts.append(
                f"{metric_name} = {value} "
                f"{unit} anomaly={anomaly}"
            )

    # --------------------------------------------------------
    # TRACES
    # --------------------------------------------------------

    traces = features.get(
        "traces",
        []
    )

    if traces:
        text_parts.append("TRACES:")

        for trace in traces:

            if not isinstance(trace, dict):
                continue

            trace_id = trace.get(
                "trace_id",
                "unknown"
            )

            text_parts.append(
                f"Trace ID: {trace_id}"
            )

            # Error spans
            error_spans = trace.get(
                "error_spans",
                []
            )

            for span in error_spans:

                if not isinstance(span, dict):
                    continue

                service = span.get(
                    "service",
                    "unknown"
                )

                operation = span.get(
                    "operation",
                    "unknown"
                )

                duration = span.get(
                    "duration_ms",
                    0
                )

                text_parts.append(
                    f"ERROR span: "
                    f"service={service}, "
                    f"operation={operation}, "
                    f"duration_ms={duration}"
                )

            # Slow spans
            slow_spans = trace.get(
                "slow_spans",
                []
            )

            for span in slow_spans:

                if not isinstance(span, dict):
                    continue

                service = span.get(
                    "service",
                    "unknown"
                )

                operation = span.get(
                    "operation",
                    "unknown"
                )

                duration = span.get(
                    "duration_ms",
                    0
                )

                text_parts.append(
                    f"SLOW span: "
                    f"service={service}, "
                    f"operation={operation}, "
                    f"duration_ms={duration}"
                )

    # --------------------------------------------------------
    # SOURCE CODE
    # --------------------------------------------------------

    source = features.get(
        "source",
        []
    )

    if source:
        text_parts.append("SOURCE CODE:")

        for unit in source:

            if not isinstance(unit, dict):
                continue

            name = unit.get(
                "name",
                "unknown"
            )

            summary = unit.get(
                "summary",
                ""
            )

            code = unit.get(
                "code",
                ""
            )

            text_parts.append(
                f"Code unit: {name}"
            )

            if summary:
                text_parts.append(
                    f"Summary: {summary}"
                )

            if code:
                text_parts.append(
                    code
                )

    return "\n".join(text_parts)


# ============================================================
# HISTORICAL INCIDENT -> TEXT
# ============================================================

def historical_incident_to_text(
    incident: dict
) -> str:
    """
    Convert a historical PostgreSQL incident record
    into text suitable for embedding.

    Root cause and resolution are intentionally excluded
    from the embedding text to avoid answer leakage.
    """

    if not isinstance(incident, dict):
        raise TypeError(
            "incident must be a dictionary"
        )

    title = incident.get(
        "title",
        ""
    )

    source = incident.get(
        "source",
        ""
    )

    severity = incident.get(
        "severity",
        ""
    )

    description = incident.get(
        "description",
        ""
    )

    text_parts = [
        f"ALERT: {title}",
        f"SERVICE: {source}",
        f"SEVERITY: {severity}",
        f"DESCRIPTION: {description}",
    ]

    return "\n".join(text_parts)


# ============================================================
# HISTORICAL INCIDENT -> EMBEDDING
# ============================================================

def generate_historical_incident_embedding(
    incident: dict
) -> list[float]:
    """
    Generate a 384-dimensional embedding for a
    historical incident.
    """

    text = historical_incident_to_text(
        incident
    )

    return generate_embedding(
        text
    )


# ============================================================
# COMPLETE INCIDENT EMBEDDING
# ============================================================

def generate_incident_embedding(
    feature_bundle: dict
) -> list[float]:
    """
    Generate an embedding for a complete incident
    feature bundle.
    """

    text = feature_bundle_to_text(
        feature_bundle
    )

    return generate_embedding(
        text
    )


# ============================================================
# MANUAL TEST
# ============================================================
