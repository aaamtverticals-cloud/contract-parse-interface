from typing import Any

def standardize_result(
    provider: str,
    filename: str,
    pages: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:

    normalized_pages = []

    for index, page in enumerate(pages, start=1):
        normalized_pages.append({
            "page_number": page.get("page_number", index),
            "text": page.get("text", ""),
            "markdown": page.get("markdown", ""),
            "tables": page.get("tables", []),
            "images": page.get("images", []),
            "metadata": page.get("metadata", {}),
        })

    return {
        "filename": filename,
        "provider": provider,
        "status": "success",
        "total_pages": len(normalized_pages),
        "parsed_pages": len(normalized_pages),
        "text": "\n\n".join(
            page["text"] for page in normalized_pages
        ),
        "markdown": "\n\n".join(
            page["markdown"] for page in normalized_pages
        ),
        "pages": normalized_pages,
        "warnings": [],
        "metadata": metadata or {},
    }