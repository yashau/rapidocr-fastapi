import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from .auth import require_api_key
from .config import Settings, get_settings
from .metrics import OCR_LATENCY, OCR_REQUESTS, OCR_UPLOAD_BYTES
from .ocr import OCRService

router = APIRouter(dependencies=[Depends(require_api_key)])

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}


def image_signature(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


class OCRLine(BaseModel):
    text: str
    score: float | None
    box: list[list[float]] | None


class OCRResponse(BaseModel):
    text: str
    lines: list[OCRLine]
    elapsed_seconds: float
    engine_elapsed_seconds: float | None
    queue_concurrency: int


def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


async def read_limited_upload(file: UploadFile, max_bytes: int) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image exceeds max upload size of {max_bytes} bytes",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def validate_image_upload(file: UploadFile, data: bytes) -> None:
    ext = _extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .png, .jpg, and .jpeg uploads are supported",
        )
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only image/png and image/jpeg content types are supported",
        )
    image_type = image_signature(data)
    if image_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file is not a valid PNG or JPEG image",
        )


@router.post("/ocr", response_model=OCRResponse)
async def ocr_image(
    request: Request,
    file: Annotated[UploadFile, File(description="PNG or JPEG image")],
    settings: Annotated[Settings, Depends(get_settings)],
):
    started = time.perf_counter()
    try:
        data = await read_limited_upload(file, settings.max_upload_bytes)
        validate_image_upload(file, data)
        OCR_UPLOAD_BYTES.observe(len(data))

        service: OCRService = request.app.state.ocr_service
        result = await service.run(data)
        OCR_REQUESTS.labels(status="ok").inc()
        OCR_LATENCY.observe(time.perf_counter() - started)
        return OCRResponse(
            text=result.text,
            lines=[OCRLine(**line) for line in result.lines],
            elapsed_seconds=result.elapsed_seconds,
            engine_elapsed_seconds=result.engine_elapsed_seconds,
            queue_concurrency=settings.ocr_concurrency,
        )
    except HTTPException:
        OCR_REQUESTS.labels(status="rejected").inc()
        raise
    except Exception as exc:
        OCR_REQUESTS.labels(status="error").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR failed",
        ) from exc
