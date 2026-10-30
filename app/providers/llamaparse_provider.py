import os
from pathlib import Path
from llama_cloud import LlamaCloud


def parse_document_sync(file_path: str) -> dict:
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {file_path}")

    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY is not configured.")

    client = LlamaCloud(api_key=api_key)

    uploaded_file = client.files.create(
        file=str(path),
        purpose="parse",
    )

    result = client.parsing.parse(
        file_id=uploaded_file.id,
        tier="agentic",
        version="latest",
        expand=["markdown"],
    )

    markdown_result = getattr(result, "markdown", None)
    raw_pages = getattr(markdown_result, "pages", []) or []

    pages = []
    markdown_parts = []

    for index, page in enumerate(raw_pages, start=1):
        page_markdown = getattr(page, "markdown", "") or ""
        markdown_parts.append(page_markdown)

        pages.append({
            "page_number": index,
            "text": page_markdown,
            "markdown": page_markdown,
            "tables": [],
            "page_success": True,
            "page_error": None,
        })

    full_markdown = "\n\n".join(markdown_parts)

    if not full_markdown.strip():
        raise ValueError(
            "LlamaParse v2 completed without returning Markdown pages. "
            "Check the parse result and requested output fields."
        )

    return {
        "filename": path.name,
        "total_pages": len(pages),
        "parsed_pages": len(pages),
        "total_tables": 0,
        "text": full_markdown,
        "markdown": full_markdown,
        "pages": pages,
        "metadata": {},
        "warnings": [
            "Structured table rows are not yet mapped in this adapter."
        ],
    }
