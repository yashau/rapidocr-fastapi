from prometheus_client import Counter, Gauge, Histogram

OCR_REQUESTS = Counter(
    "rapidocr_requests_total",
    "OCR requests by outcome.",
    ["status"],
)

OCR_LATENCY = Histogram(
    "rapidocr_request_seconds",
    "OCR request latency in seconds.",
    buckets=(0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5, 10, 30),
)

OCR_QUEUE_WAIT = Histogram(
    "rapidocr_queue_wait_seconds",
    "Time spent waiting for OCR concurrency slot.",
    buckets=(0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

OCR_UPLOAD_BYTES = Histogram(
    "rapidocr_upload_bytes",
    "Uploaded image size in bytes.",
    buckets=(
        10_000,
        50_000,
        100_000,
        250_000,
        500_000,
        1_000_000,
        2_500_000,
        5_000_000,
        10_000_000,
    ),
)

OCR_IN_FLIGHT = Gauge(
    "rapidocr_in_flight",
    "OCR requests currently being processed.",
)

OCR_QUEUE_DEPTH = Gauge(
    "rapidocr_queue_depth",
    "Approximate number of requests waiting on OCR concurrency.",
)
