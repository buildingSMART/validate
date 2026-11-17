from dataclasses import replace

from ..datamodel.ui import Dashboard, DashboardOptions


def can_delete(status: str, progress: int | None) -> bool:
    # Match the v1 dashboard, and enforce the same rule again at mutation time.
    return status in ("PENDING", "FAILED") or (progress is not None and progress >= 100)


def build_dashboard(inputs, total: int, options: DashboardOptions,
                    selected: tuple[str, ...]) -> Dashboard:
    entries = tuple(replace(item, can_delete=can_delete(item.status, item.progress),
                            selected=item.request_id in selected) for item in inputs)
    start = (options.page - 1) * options.per_page
    visible_ids = {item.request_id for item in entries}
    return Dashboard(entries, options, total, start + 1 if total else 0, min(start + len(entries), total),
                     options.page - 1 if options.page > 1 else None,
                     options.page + 1 if start + len(entries) < total else None,
                     any(item.status not in ("COMPLETED", "FAILED") or item.pdf_pending for item in inputs),
                     selected, tuple(id for id in selected if id not in visible_ids))
