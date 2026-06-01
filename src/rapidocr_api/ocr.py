import asyncio
import io
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image
from rapidocr import RapidOCR

from .config import Settings
from .metrics import OCR_IN_FLIGHT, OCR_QUEUE_DEPTH, OCR_QUEUE_WAIT


@dataclass
class OCRResult:
    text: str
    lines: list[dict[str, Any]]
    elapsed_seconds: float
    engine_elapsed_seconds: float | None


class OCRService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine = RapidOCR()
        self._semaphore = asyncio.Semaphore(settings.ocr_concurrency)
        self._waiting = 0

    async def run(self, image_bytes: bytes) -> OCRResult:
        wait_started = time.perf_counter()
        self._waiting += 1
        OCR_QUEUE_DEPTH.set(self._waiting)
        try:
            async with self._semaphore:
                waited = time.perf_counter() - wait_started
                OCR_QUEUE_WAIT.observe(waited)
                self._waiting -= 1
                OCR_QUEUE_DEPTH.set(self._waiting)
                OCR_IN_FLIGHT.inc()
                try:
                    started = time.perf_counter()
                    result = await asyncio.to_thread(self._run_sync, image_bytes)
                    result.elapsed_seconds = time.perf_counter() - started
                    return result
                finally:
                    OCR_IN_FLIGHT.dec()
        finally:
            if self._waiting < 0:
                self._waiting = 0
                OCR_QUEUE_DEPTH.set(0)

    def _run_sync(self, image_bytes: bytes) -> OCRResult:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.asarray(image)
        result = self._engine(arr, use_cls=self.settings.rapidocr_use_cls)
        texts = list(getattr(result, "txts", []) or [])
        scores = list(getattr(result, "scores", []) or [])
        boxes = getattr(result, "boxes", None)
        lines = []

        for index, text in enumerate(texts):
            box_value = None
            if boxes is not None and index < len(boxes):
                box_value = np.asarray(boxes[index]).round(2).tolist()
            score_value = None
            if index < len(scores):
                score_value = float(scores[index])
            lines.append(
                {
                    "text": str(text),
                    "score": score_value,
                    "box": box_value,
                }
            )

        return OCRResult(
            text="\n".join(texts),
            lines=lines,
            elapsed_seconds=0.0,
            engine_elapsed_seconds=(
                float(result.elapse) if getattr(result, "elapse", None) is not None else None
            ),
        )
