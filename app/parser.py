
import asyncio
import importlib
import os
from pathlib import Path

DEFAULT_PROVIDER = "docling"


def parse_document_sync(file_path: str) -> dict:
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {file_path}")

    if path.stat().st_size == 0:
        raise ValueError("The uploaded document is empty.")

    provider_name = os.getenv(
        "PARSER_PROVIDER", DEFAULT_PROVIDER
    ).strip().lower()

    allowed_providers = {
        "docling": "app.providers.docling_provider",
        "llamaparse": "app.providers.llamaparse_provider",
        "mistral": "app.providers.mistral_provider",
    }

    module_path = allowed_providers.get(provider_name)

    if module_path is None:
        raise ValueError(
            f"Unsupported parser provider: {provider_name}. "
            f"Choose one of: {', '.join(allowed_providers)}"
        )

    provider_module = importlib.import_module(module_path)
    provider_parser = provider_module.parse_document_sync

    result = provider_parser(str(path))
    if not isinstance(result, dict):
        raise TypeError("Provider must return a dictionary.")

    required_keys = {
        "filename",
        "total_pages",
        "parsed_pages",
        "total_tables",
        "text",
        "markdown",
        "pages",
        "metadata",
        "warnings",
    }

    missing = required_keys - result.keys()

    if missing:
        raise ValueError(
            f"Provider '{provider_name}' is missing fields: "
            f"{', '.join(sorted(missing))}"
        )

    if not isinstance(result["pages"], list):
        raise ValueError("Provider must return pages as a list.")

    if not result["pages"]:
        raise ValueError("No pages were returned by the parser.")

    return result

async def parse_document(file_path: str) -> dict:
    return await asyncio.to_thread(
        parse_document_sync, file_path
    )