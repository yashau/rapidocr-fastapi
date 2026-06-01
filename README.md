# rapidocr-fastapi

FastAPI service for running RapidOCR through a small, deployable HTTP API.

`rapidocr-fastapi` is designed for private OCR workloads that need a warm local worker, predictable resource usage, and a simple integration surface. It accepts PNG and JPEG uploads, runs OCR through RapidOCR, and returns extracted text plus per-line confidence and bounding boxes.

## Highlights

- Warm RapidOCR worker behind `POST /v1/ocr`
- API-key authentication with `X-API-Key` or bearer tokens
- Configurable OCR concurrency to protect the host
- Upload size limits with PNG/JPEG signature validation
- Prometheus-compatible metrics at `/metrics`
- OpenAPI schema, Swagger UI, and ReDoc included
- Docker Compose setup with localhost binding by default
- TOML-based API key management with a built-in key generator

## Quick Start

```bash
cp .env.example .env
cp api-keys.example.toml api-keys.toml
uv sync
uv run rapidocr-api
```

Open the API docs:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

Send an OCR request:

```bash
curl -H "X-API-Key: dev-key-change-me" \
  -F "file=@/path/to/image.png" \
  http://localhost:8000/v1/ocr
```

## Docker Compose

Start the service:

```bash
cp api-keys.example.toml api-keys.toml
docker compose up --build
```

Compose publishes the service on `127.0.0.1:8000` by default. Override the bind address, port, memory, CPU, or OCR thread count with environment variables:

```bash
HOST_BIND=0.0.0.0 HOST_PORT=8080 docker compose up --build
MEM_LIMIT=3g CPU_LIMIT=4 OCR_THREADS=4 docker compose up --build
```

| Setting | Default |
|---|---:|
| `HOST_BIND` | `127.0.0.1` |
| `HOST_PORT` | `8000` |
| `MEM_LIMIT` | `4g` |
| `CPU_LIMIT` | `6` |
| `OCR_THREADS` | `6` |

## API Keys

API keys are stored in `api-keys.toml`, not in `.env`.

```toml
api_keys = [
  # Production key.
  "replace-with-long-random-key",
]
```

Generate and append a new key:

```bash
uv run rapidocr-add-key
```

The command prompts for a comment, writes it above the generated key, and prints the key once.

The service reads `api-keys.toml` on each authenticated request, so adding or removing keys does not require a restart.

Nested TOML is also supported:

```toml
[auth]
api_keys = [
  "replace-with-long-random-key",
]
```

Authentication is disabled if the key file is missing or empty.

## Configuration

| Env var | Default | Description |
|---|---:|---|
| `API_KEYS_FILE` | `api-keys.toml` | TOML file containing API keys. |
| `OCR_CONCURRENCY` | `1` | OCR jobs allowed at once per process. |
| `MAX_UPLOAD_BYTES` | `5242880` | Maximum accepted upload size. |
| `RAPIDOCR_USE_CLS` | `false` | Enables RapidOCR textline orientation classification. |
| `ENABLE_METRICS` | `true` | Exposes `/metrics`. |
| `METRICS_REQUIRE_API_KEY` | `false` | Protects `/metrics` with API-key auth. |
| `WEBUI_DIR` | unset | Optional static web UI directory mounted at `/`. |

## Response Shape

`POST /v1/ocr` returns the combined text, individual OCR lines, confidence scores, bounding boxes, and timing information:

```json
{
  "text": "Example text",
  "lines": [
    {
      "text": "Example text",
      "score": 0.99,
      "box": [[10, 20], [120, 20], [120, 45], [10, 45]]
    }
  ],
  "elapsed_seconds": 0.72,
  "engine_elapsed_seconds": 0.68,
  "queue_concurrency": 1
}
```

## Metrics

Scrape `/metrics` with Prometheus, Grafana Alloy, or another Prometheus-compatible collector.

| Metric | Description |
|---|---|
| `rapidocr_requests_total` | OCR requests by status. |
| `rapidocr_request_seconds` | End-to-end OCR request latency. |
| `rapidocr_queue_wait_seconds` | Time spent waiting for an OCR slot. |
| `rapidocr_upload_bytes` | Uploaded image size distribution. |
| `rapidocr_in_flight` | OCR requests currently being processed. |
| `rapidocr_queue_depth` | Approximate requests waiting for OCR. |

## Operational Notes

The OCR concurrency limit is per Uvicorn worker process. Run a single worker when `OCR_CONCURRENCY=1` must be enforced globally inside one container.
