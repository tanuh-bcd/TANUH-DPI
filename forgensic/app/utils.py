"""
Shared serialization helpers for the forgensic API and Celery tasks.

Extracted from main.py so neither main.py nor tasks.py imports each other
(avoiding circular dependencies).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from .pipeline import DetectedRegion, DocumentPage, PageAnalysisResult


def region_to_dict(region: DetectedRegion) -> Dict[str, Any]:
    return {
        "x": region.x,
        "y": region.y,
        "w": region.w,
        "h": region.h,
        "category_id": region.category_id,
        "type": region.type,
        "stretch_factor": region.stretch_factor,
        "header_source": region.header_source,
        "body_source": region.body_source,
    }


def result_to_dict(
    result: PageAnalysisResult,
    page: Optional[DocumentPage],
    image_url: Optional[str],
    preview_url: Optional[str],
) -> Dict[str, Any]:
    return {
        "page_id": f"{result.file_name}",
        "page_number": result.page_number,
        "file_name": result.file_name,
        "image_url": image_url,
        "preview_url": preview_url,
        "image_width": page.image_width if page else None,
        "image_height": page.image_height if page else None,
        "categories": result.predicted_categories,
        "regions": [region_to_dict(r) for r in result.detected_regions],
        "notes": result.notes,
    }


def build_results_payload(
    job_id: str,
    file_name: str,
    pages: List[DocumentPage],
    results: List[PageAnalysisResult],
    export_info: Dict[str, Any],
    file_url_map: Dict[str, str],
    preview_url_map: Dict[str, str],
    pipeline_version: str,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    findings_summary: Optional[Dict[str, Any]] = None,
    inference_seconds: Optional[float] = None,
    avg_inference_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the full JSON-serializable result payload for a completed job."""
    page_map = {p.page_file_name: p for p in pages}
    payload_pages = []
    summary: Dict[str, int] = {}

    for res in results:
        page = page_map.get(res.file_name)
        image_url = file_url_map.get(res.file_name)
        preview_url = preview_url_map.get(res.file_name)
        payload_pages.append(result_to_dict(res, page, image_url, preview_url))
        for cat in res.predicted_categories:
            summary[cat] = summary.get(cat, 0) + 1

    export_urls: Dict[str, Any] = {
        "json": file_url_map.get("submission.json"),
        "excel": file_url_map.get("submission_preview.xlsx"),
        "yaml": [
            file_url_map.get(Path(p).name)
            for p in export_info.get("yaml_paths", [])
            if file_url_map.get(Path(p).name)
        ],
    }
    if not any([export_urls.get("json"), export_urls.get("excel"), export_urls.get("yaml")]):
        export_urls = {}

    return {
        "job_id": job_id,
        "status": "complete",
        "file_name": file_name,
        "pipeline_version": pipeline_version,
        "pages": payload_pages,
        "category_summary": summary,
        "export_urls": export_urls,
        "findings_summary": findings_summary,
        "inference_seconds": inference_seconds,
        "avg_inference_seconds": avg_inference_seconds,
        "created_at": created_at,
        "updated_at": updated_at,
    }
