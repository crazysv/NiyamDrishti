"""Prometheus metrics registry and instrumentation for NiyamDrishti."""

import time
from typing import Callable, Any
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

# Custom Registry for NiyamDrishti metrics (can also use default REGISTRY)
# Using standard REGISTRY so standard Python process/GC metrics are included if desired.
registry = REGISTRY

# ---------------------------------------------------------------------------
# HTTP & API Metrics
# ---------------------------------------------------------------------------
http_requests_total = Counter(
    "niyamdrishti_http_requests_total",
    "Total count of HTTP requests processed by NiyamDrishti API",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "niyamdrishti_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=registry,
)

active_requests = Gauge(
    "niyamdrishti_active_requests",
    "Current number of active in-flight HTTP requests",
    registry=registry,
)

# ---------------------------------------------------------------------------
# Core Legal Metrology & Domain Metrics
# ---------------------------------------------------------------------------
inspections_total = Counter(
    "niyamdrishti_inspections_total",
    "Total completed inspections by overall verdict and category",
    ["overall_verdict", "commodity_category", "is_self_check"],
    registry=registry,
)

ocr_processing_duration_seconds = Histogram(
    "niyamdrishti_ocr_processing_duration_seconds",
    "OCR image processing latency in seconds",
    ["engine", "status"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0],
    registry=registry,
)

rule_evaluation_duration_seconds = Histogram(
    "niyamdrishti_rule_evaluation_duration_seconds",
    "Rule engine evaluation duration in seconds",
    ["rule_pack_version"],
    buckets=[0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=registry,
)

offline_sync_operations_total = Counter(
    "niyamdrishti_offline_sync_operations_total",
    "Total offline sync items processed",
    ["entity_type", "status"],  # entity_type: inspection | image; status: synced | conflict | skipped | failed
    registry=registry,
)

quality_gate_checks_total = Counter(
    "niyamdrishti_quality_gate_checks_total",
    "Image quality gate evaluations",
    ["result", "role"],  # result: pass | blur | glare | underexposed | low_resolution
    registry=registry,
)

report_generation_duration_seconds = Histogram(
    "niyamdrishti_report_generation_duration_seconds",
    "Inspection PDF report generation latency in seconds",
    ["renderer"],  # weasyprint | fpdf2
    buckets=[0.2, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=registry,
)


def get_latest_metrics() -> tuple[bytes, str]:
    """Generate latest Prometheus metrics in text exposition format."""
    return generate_latest(registry), CONTENT_TYPE_LATEST


def record_ocr_duration(duration_seconds: float, engine: str = "paddleocr", status: str = "success") -> None:
    """Safely record OCR processing duration."""
    try:
        ocr_processing_duration_seconds.labels(engine=engine, status=status).observe(duration_seconds)
    except Exception:
        pass


def record_rule_evaluation_duration(duration_seconds: float, rule_pack_version: str = "2026.02.01") -> None:
    """Safely record rule evaluation latency."""
    try:
        rule_evaluation_duration_seconds.labels(rule_pack_version=rule_pack_version).observe(duration_seconds)
    except Exception:
        pass


def record_inspection_completed(verdict: str, category: str = "general", is_self_check: bool = False) -> None:
    """Safely record completed inspection counter."""
    try:
        inspections_total.labels(
            overall_verdict=verdict,
            commodity_category=category or "unknown",
            is_self_check=str(is_self_check).lower(),
        ).inc()
    except Exception:
        pass


def record_offline_sync(entity_type: str, status: str, count: int = 1) -> None:
    """Safely record offline sync operations."""
    try:
        offline_sync_operations_total.labels(entity_type=entity_type, status=status).inc(count)
    except Exception:
        pass
