import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from app.parser import parse_document

load_dotenv()

APP_NAME = "Contract Parsing API"
MAX_FILE_SIZE = 50 * 1024 * 1024  

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "log.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=APP_NAME,
    description=(
        "Extracts document text, Markdown, and recognized tables "
        "from PDF and Word documents."
    ),
    version="1.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5174",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def write_log(entry: dict[str, Any]) -> None:
    try:
        entries = []

        if LOG_FILE.exists():
            try:
                existing = json.loads(
                    LOG_FILE.read_text(encoding="utf-8")
                )
                if isinstance(existing, list):
                    entries = existing
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not read existing log.json")

        entries.append(entry)

        LOG_FILE.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    except OSError:
        logger.exception("Unable to write API log")


def detect_format(file_path: Path) -> str:
    with file_path.open("rb") as file:
        signature = file.read(8)

    # PDF signature
    if signature.startswith(b"%PDF-"):
        return "pdf"
    if signature.startswith(b"PK\x03\x04"):
        try:
            import zipfile

            with zipfile.ZipFile(file_path) as archive:
                names = set(archive.namelist())

            if "word/document.xml" in names:
                return "docx"

            return "unsupported_zip"
        except (OSError, zipfile.BadZipFile):
            return "invalid_zip"
    if signature.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        return "doc"

    return "unknown"

def get_page_count(parsed_document: dict) -> int:
    pages = parsed_document.get("pages", [])
    if isinstance(pages, list) and pages:
        return len(pages)

    return int(parsed_document.get("total_pages") or 0)

def get_parsed_page_count(parsed_document: dict) -> int:
    pages = parsed_document.get("pages", [])

    if not isinstance(pages, list):
        return 0

    return sum(
        1
        for page in pages
        if isinstance(page, dict)
        and page.get("page_success") is not False
        and not page.get("page_error")
    )

def get_table_count(parsed_document: dict) -> int:
    pages = parsed_document.get("pages", [])

    if isinstance(pages, list):
        return sum(
            len(page.get("tables", []))
            for page in pages
            if isinstance(page, dict)
            and isinstance(page.get("tables", []), list)
        )

    return int(parsed_document.get("total_tables") or 0)

def build_quality(parsed_document: dict) -> dict:
    pages = parsed_document.get("pages", [])
    page_count = get_page_count(parsed_document)
    parsed_count = get_parsed_page_count(parsed_document)
    table_count = get_table_count(parsed_document)

    page_errors = [
        page
        for page in pages
        if isinstance(page, dict)
        and (
            page.get("page_success") is False
            or page.get("page_error")
        )
    ] if isinstance(pages, list) else []

    return {
        "text_extraction": (
            "complete"
            if page_count > 0 and parsed_count == page_count
            else "partial" if parsed_count > 0 else "failed"
        ),
        "table_extraction": (
            "recognized"
            if table_count > 0
            else "none_detected"
        ),
        "structured_extraction": "not_run",
        "validation": "not_run",
        "page_errors": len(page_errors),
        "note": (
            "Recognition counts do not prove that every source page, "
            "table, or cell was extracted correctly."
        ),
    }

@app.get("/")
async def root():
    return {
        "name": APP_NAME,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "parse": "/api/parse",
            "docs": "/docs",
        },
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    request_id = str(uuid.uuid4())
    started_at = time.perf_counter()
    temp_path = None

    original_filename = Path(file.filename or "upload").name
    extension = Path(original_filename).suffix.lower()

    log_entry = {
        "request_id": request_id,
        "filename": original_filename,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=(
                    "Unsupported file extension. "
                    "Upload a PDF, DOCX, or DOC file."
                ),
            )
        total_size = 0

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:
            temp_path = Path(temp_file.name)

            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds the 15 MB size limit.",
                    )

                temp_file.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )
        detected_format = detect_format(temp_path)

        if detected_format == "unknown":
            raise HTTPException(
                status_code=415,
                detail=(
                    "Could not identify the file format from its "
                    "signature. Check that the file is valid."
                ),
            )

        if detected_format == "unsupported_zip":
            raise HTTPException(
                status_code=415,
                detail=(
                    "This ZIP-based file is not recognized as a DOCX. "
                    "Upload a supported document."
                ),
            )

        if detected_format == "invalid_zip":
            raise HTTPException(
                status_code=400,
                detail="The uploaded Office document is corrupted.",
            )
        if extension == ".pdf" and detected_format != "pdf":
            raise HTTPException(
                status_code=415,
                detail="The file extension does not match its PDF content.",
            )

        if extension == ".docx" and detected_format != "docx":
            raise HTTPException(
                status_code=415,
                detail="The file extension does not match its DOCX content.",
            )

        if extension == ".doc" and detected_format not in {"doc", "docx"}:
            raise HTTPException(
                status_code=415,
                detail="The file extension does not match a supported Word document.",
            )
        parsed_document = await parse_document(str(temp_path))

        if not isinstance(parsed_document, dict):
            raise RuntimeError(
                "The parser returned an unexpected response format."
            )
        pages = parsed_document.get("pages", [])
        if not isinstance(pages, list):
            pages = []

        total_pages = len(pages)
        parsed_pages = get_parsed_page_count(parsed_document)
        total_tables = get_table_count(parsed_document)
        parsed_document["total_pages"] = total_pages
        parsed_document["parsed_pages"] = parsed_pages
        parsed_document["total_tables"] = total_tables

        quality = build_quality(parsed_document)

        if total_pages == 0:
            status = "failed"
        elif parsed_pages < total_pages:
            status = "partial"
        else:
            status = "success"

        elapsed_seconds = round(
            time.perf_counter() - started_at,
            3,
        )

        response = {
            "status": status,
            "request_id": request_id,
            "document": {
                "filename": original_filename,
                "detected_format": detected_format,
                "file_size_bytes": total_size,
                "total_pages": total_pages,
                "parsed_pages": parsed_pages,
                "total_tables": total_tables,
            },
            "quality": quality,
            "parsed_document": parsed_document,
            "processing_time_seconds": elapsed_seconds,
        }

        log_entry.update({
            "status": status,
            "detected_format": detected_format,
            "file_size_bytes": total_size,
            "total_pages": total_pages,
            "parsed_pages": parsed_pages,
            "total_tables": total_tables,
            "processing_time_seconds": elapsed_seconds,
        })

        write_log(log_entry)

        if status == "failed":
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "No pages were returned by the parser.",
                    "request_id": request_id,
                },
            )

        return response

    except HTTPException as exc:
        log_entry.update({
            "status": "failed",
            "http_status": exc.status_code,
            "error": exc.detail,
        })
        write_log(log_entry)
        raise

    except Exception as exc:
        logger.exception(
            "Document parsing failed. request_id=%s",
            request_id,
        )

        log_entry.update({
            "status": "failed",
            "error": str(exc),
        })
        write_log(log_entry)

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Document parsing failed.",
                "request_id": request_id,
                "error": str(exc),
            },
        ) from exc

    finally:
        await file.close()

        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logger.warning(
                    "Could not delete temporary file: %s",
                    temp_path,
                )