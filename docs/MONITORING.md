# MONITORING — Observability, Metrics & Alerting Guide

> Authoritative reference for NiyamDrishti's production monitoring stack (`E4-03`, `MASTER_CONTENT.md` §11.9, `03_TECHSPEC.md`).
> Built on a 100% free, self-hostable stack (Prometheus v2.53.0 + Grafana v11.0.0) with zero external vendor dependencies or paid licensing traps.

---

## 1. Architecture Overview

```
                          ┌────────────────────────┐
                          │   Next.js Frontend     │
                          │ (Injects X-Request-ID) │
                          └───────────┬────────────┘
                                      │ HTTP REST
                                      ▼
                          ┌────────────────────────┐
                          │    FastAPI Backend     │
                          │ ObservabilityMiddleware│
                          │   - Request Timing     │
                          │   - Cardinality Guard  │
                          │   - Domain Metrics     │
                          └───────────┬────────────┘
                                      │ /metrics (Text format)
                                      ▼
                          ┌────────────────────────┐
                          │  Prometheus (Scraper)  │
                          │  15s scrape interval   │
                          │  Pre-configured Alerts │
                          └───────────┬────────────┘
                                      │ PromQL
                                      ▼
                          ┌────────────────────────┐
                          │   Grafana Dashboards   │
                          │  Port 3001 (Overview)  │
                          └────────────────────────┘
```

---

## 2. Metric Catalog & Semantics

All NiyamDrishti metrics are prefixed with `niyamdrishti_` to guarantee clear separation from standard Python process and system metrics:

| Metric Name | Type | Labels | Purpose / Semantics |
|---|---|---|---|
| `niyamdrishti_http_requests_total` | Counter | `method`, `endpoint`, `status_code` | Aggregate HTTP throughput and error rates. Endpoints are strictly normalized (e.g. `{id}`). |
| `niyamdrishti_http_request_duration_seconds` | Histogram | `method`, `endpoint` | End-to-end request duration percentiles (P50, P95, P99) with buckets: `[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]`. |
| `niyamdrishti_active_requests` | Gauge | — | Real-time gauge of in-flight requests currently being handled. |
| `niyamdrishti_inspections_total` | Counter | `overall_verdict`, `commodity_category`, `is_self_check` | Legal Metrology statutory throughput, compliance vs non-compliance ratio, and manufacturer self-check volume. |
| `niyamdrishti_ocr_processing_duration_seconds` | Histogram | `engine`, `status` | Core OCR execution latency (PaddleOCR / Tesseract) with buckets up to 15s. |
| `niyamdrishti_rule_evaluation_duration_seconds` | Histogram | `rule_pack_version` | Mathematical evaluation duration across all statutory rules in the active rule-pack. |
| `niyamdrishti_offline_sync_operations_total` | Counter | `entity_type`, `status` | Offline batch sync operations (`entity_type: inspection \| image`; `status: synced \| conflict \| skipped \| failed`). |
| `niyamdrishti_quality_gate_checks_total` | Counter | `result`, `role` | Camera quality gate pass vs rejection tallies (blur, glare, underexposure). |
| `niyamdrishti_report_generation_duration_seconds` | Histogram | `renderer` | Evidentiary PDF inspection certificate generation duration (`weasyprint` / `fpdf2`). |

---

## 3. Metric Cardinality Guardrails

In compliance with production Prometheus best practices, NiyamDrishti enforces **low-cardinality endpoint labeling**:
- Dynamically generated IDs (such as UUIDs, inspection IDs `insp_...`, image IDs `img_...`, integer IDs) are never used as raw label values.
- `ObservabilityMiddleware` queries FastAPI route templates (e.g. `/api/v1/inspections/{inspection_id}`) or uses regex path maskers to replace dynamic segments with `{id}`.
- This ensures Prometheus memory consumption remains bounded and stable regardless of millions of unique inspections.

---

## 4. Correlation ID Tracing (`X-Request-ID`)

- Every request is tagged with an `X-Request-ID` header.
- If a client (e.g. frontend PWA or mobile wrapper) sends an existing `X-Request-ID`, it is preserved across the lifecycle.
- If missing, `ObservabilityMiddleware` automatically mints a new UUID4.
- The `X-Request-ID` is returned in the response header and attached to `request.state.request_id` for inclusion in structured application logs.

---

## 5. Health Probes

NiyamDrishti provides three dedicated health probe endpoints for container runtimes, Kubernetes, and reverse proxies:

| Endpoint | Target / Use Case | Expected Response | Failure Code |
|---|---|---|---|
| `GET /health` | Comprehensive administrative health probe | `{"status": "ok", "env": "...", "version": "0.1.0", "uptime_seconds": ..., "database": {...}}` | 200 (degraded status payload) |
| `GET /health/live` | Container liveness check | `{"status": "alive"}` | 500 / unhandled |
| `GET /health/ready` | Container readiness check (DB connected) | `{"status": "ready", "database": {...}}` | 503 Service Unavailable |

---

## 6. Pre-Configured Alerting Rules

Stored in `monitoring/prometheus/alert_rules.yml`:

| Alert | Condition | Severity | Description |
|---|---|---|---|
| **`BackendApiDown`** | `up{job="niyamdrishti-api"} == 0` for 1m | Critical | Backend API is unreachable from Prometheus. |
| **`HighHttp5xxErrorRate`** | 5xx rate > 5% over 2m | Critical | Internal server error rate exceeds acceptable threshold. |
| **`HighP95Latency`** | P95 latency > 3.0s over 3m | Warning | API responses are degrading in latency. |
| **`SlowOcrEngineProcessing`** | OCR P95 > 8.0s over 3m | Warning | Image OCR engine pipeline is backlogged or slow. |
| **`HighOfflineSyncConflictRate`** | HTTP 409 conflict rate > 15% over 5m | Warning | Field devices are attempting to sync stale edits against completed cases. |

---

## 7. Self-Hosted Deployment & Quickstart

To run the complete monitoring stack locally or on a dedicated server:

```bash
cd docker

# Option A: Start monitoring alongside core dev stack using profile
docker compose --profile monitoring up -d

# Option B: Explicitly specify monitoring overlay
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Endpoints:
- **FastAPI Metrics:** `http://localhost:8000/metrics`
- **Prometheus Dashboard & Targets:** `http://localhost:9090`
- **Grafana Observability Portal:** `http://localhost:3001`
  - Default credentials: `admin` / `niyamdrishti`
  - Dashboard: **NiyamDrishti — Production Observability** (auto-provisioned)
