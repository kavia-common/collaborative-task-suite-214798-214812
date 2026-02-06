from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from .models import ActivityLog, Project, Task, Team

logger = logging.getLogger(__name__)


# PUBLIC_INTERFACE
def create_activity_log(
    *,
    actor,
    event_type: str,
    message: str = "",
    team: Team | None = None,
    project: Project | None = None,
    task: Task | None = None,
    metadata: dict[str, Any] | None = None,
) -> ActivityLog:
    """Create an activity log entry with best-effort error handling.

    This helper is intentionally resilient: activity logging must never break
    primary request flows.
    """
    try:
        return ActivityLog.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            event_type=event_type,
            message=message,
            team=team,
            project=project,
            task=task,
            metadata=metadata or {},
            created_at=timezone.now(),
        )
    except Exception:
        logger.exception("Failed to create ActivityLog event_type=%s", event_type)
        # Best-effort: swallow exceptions
        return ActivityLog(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            event_type=event_type,
            message=message,
            team=team,
            project=project,
            task=task,
            metadata=metadata or {},
        )
