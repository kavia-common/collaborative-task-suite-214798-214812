from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base model that adds created/updated timestamps."""
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class Team(TimeStampedModel):
    """A workspace that groups users and projects."""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teams_created",
    )

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Team({self.id}): {self.name}"


class TeamMembership(TimeStampedModel):
    """A user's membership in a team, including their role."""
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        unique_together = ("team", "user")
        indexes = [
            models.Index(fields=["team", "user"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"TeamMembership(team={self.team_id}, user={self.user_id}, role={self.role})"


class Project(TimeStampedModel):
    """A project within a team."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="projects_created",
    )

    class Meta:
        unique_together = ("team", "name")
        indexes = [
            models.Index(fields=["team", "name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Project({self.id}): {self.name}"


class ProjectMembership(TimeStampedModel):
    """A user's membership in a project (subset of team)."""
    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        CONTRIBUTOR = "contributor", "Contributor"
        VIEWER = "viewer", "Viewer"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CONTRIBUTOR)

    class Meta:
        unique_together = ("project", "user")
        indexes = [
            models.Index(fields=["project", "user"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"ProjectMembership(project={self.project_id}, user={self.user_id}, role={self.role})"


class Task(TimeStampedModel):
    """A work item within a project."""
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"
        URGENT = 4, "Urgent"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.IntegerField(choices=Priority.choices, default=Priority.MEDIUM)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tasks_created",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks_assigned",
    )

    due_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "priority"]),
            models.Index(fields=["assignee"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Task({self.id}): {self.title}"

    def mark_done(self) -> None:
        """Mark task as done and set completed timestamp."""
        self.status = self.Status.DONE
        self.completed_at = timezone.now()


class Comment(TimeStampedModel):
    """A comment on a task."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comments_authored",
    )
    body = models.TextField()

    class Meta:
        indexes = [
            models.Index(fields=["task", "created_at"]),
            models.Index(fields=["author"]),
        ]

    def __str__(self) -> str:
        return f"Comment({self.id}) on Task({self.task_id})"


class ActivityLog(TimeStampedModel):
    """An audit/activity trail event (team/project/task scoped)."""
    class EventType(models.TextChoices):
        TEAM_CREATED = "team_created", "Team created"
        TEAM_MEMBER_ADDED = "team_member_added", "Team member added"
        PROJECT_CREATED = "project_created", "Project created"
        PROJECT_MEMBER_ADDED = "project_member_added", "Project member added"
        TASK_CREATED = "task_created", "Task created"
        TASK_UPDATED = "task_updated", "Task updated"
        TASK_STATUS_CHANGED = "task_status_changed", "Task status changed"
        TASK_COMMENTED = "task_commented", "Task commented"
        AI_PRIORITY_SUGGESTED = "ai_priority_suggested", "AI priority suggested"
        AI_DELAY_RISK_PREDICTED = "ai_delay_risk_predicted", "AI delay risk predicted"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    message = models.TextField(blank=True)

    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name="activity_logs")
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True, blank=True, related_name="activity_logs"
    )
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name="activity_logs")

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["team", "created_at"]),
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["task", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"ActivityLog({self.id}): {self.event_type}"
