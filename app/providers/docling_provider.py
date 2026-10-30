import logging
from pathlib import Path
from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

def parse_document_sync(file_path: str) -> dict:
    path = Path(file_path)

    converter = DocumentConverter()
    result = converter.convert(str(path))
    document = result.document

    full_markdown = document.export_to_markdown()
    exported = document.export_to_dict()

    raw_pages = getattr(document, "pages", {})
    page_numbers = []

    if isinstance(raw_pages, dict):
        for key in raw_pages:
            try:
                page_numbers.append(int(key))
            except (TypeError, ValueError):
                continue

    page_map = {}

    def ensure_page(page_no):
        if page_no not in page_map:
            page_map[page_no] = {
                "page_number": page_no,
                "text": "",
                "markdown": "",
                "tables": [],
                "page_success": True,
                "page_error": None,
            }

    for page_no in page_numbers:
        ensure_page(page_no)
    for item in getattr(document, "texts", []):
        text = getattr(item, "text", "") or ""

        for prov in getattr(item, "prov", []) or []:
            try:
                page_no = int(prov.page_no)
            except (AttributeError, TypeError, ValueError):
                continue

            ensure_page(page_no)

            if text:
                page_map[page_no]["text"] += text + "\n"
                page_map[page_no]["markdown"] += text + "\n"
    total_tables = 0

    for table_index, table in enumerate(
        getattr(document, "tables", []), start=1
    ):
        try:
            grid = table.data.grid
            rows = [
                [
                    str(getattr(cell, "text", cell) or "")
                    for cell in row
                ]
                for row in grid
            ]
            table_markdown = table.export_to_markdown()
        except Exception as exc:
            logger.warning(
                "Table %s extraction failed: %s", table_index, exc
            )
            continue

        provenance = getattr(table, "prov", []) or []
        table_pages = set()

        for prov in provenance:
            try:
                table_pages.add(int(prov.page_no))
            except (AttributeError, TypeError, ValueError):
                continue

        if not table_pages:
            table_pages = {min(page_map) if page_map else 1}

        for page_no in sorted(table_pages):
            ensure_page(page_no)

            table_entry = {
                "table_id": f"P{page_no:03}-T{table_index:03}",
                "page_number": page_no,
                "row_count": len(rows),
                "column_count": max(
                    (len(row) for row in rows), default=0
                ),
                "headers": rows[0] if rows else [],
                "rows": rows,
                "markdown": table_markdown,
                "html": None,
                "csv": None,
                "bbox": None,
                "parse_concerns": [],
            }

            page_map[page_no]["tables"].append(table_entry)

            if table_markdown:
                page_map[page_no]["markdown"] += (
                    "\n" + table_markdown + "\n"
                )

            total_tables += 1
    if not page_map:
        ensure_page(1)
        page_map[1]["text"] = full_markdown or ""
        page_map[1]["markdown"] = full_markdown or ""

    pages = [
        page_map[number] for number in sorted(page_map)
    ]

    return {
        "filename": path.name,
        "total_pages": len(pages),
        "parsed_pages": sum(
            1 for page in pages
            if page["page_success"] is not False
        ),
        "total_tables": total_tables,
        "text": full_markdown,
        "markdown": full_markdown,
        "pages": pages,
        "metadata": exported.get("metadata", {}),
        "warnings": [],
    }
