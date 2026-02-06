from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    ActivityLog,
    Comment,
    Project,
    ProjectMembership,
    Task,
    Team,
    TeamMembership,
)

User = get_user_model()


class UserPublicSerializer(serializers.ModelSerializer):
    """A minimal user representation safe for API exposure."""

    class Meta:
        model = User
        fields = ["id", "username", "email"]


class RegisterSerializer(serializers.Serializer):
    """Registration payload."""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)


class LoginSerializer(serializers.Serializer):
    """Login payload."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class TeamSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = Team
        fields = ["id", "name", "description", "created_by", "created_at", "updated_at"]


class TeamMembershipSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "team", "user", "role", "created_at", "updated_at"]
        read_only_fields = ["team"]


class TeamMembershipCreateSerializer(serializers.ModelSerializer):
    """Create membership by specifying a user id."""
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "team", "user_id", "role", "created_at", "updated_at"]
        read_only_fields = ["id", "team", "created_at", "updated_at"]

    def validate_user_id(self, value: int) -> int:
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User not found.")
        return value


class ProjectSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = Project
        fields = ["id", "team", "name", "description", "created_by", "created_at", "updated_at"]
        read_only_fields = ["team"]


class ProjectMembershipSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "project", "user", "role", "created_at", "updated_at"]
        read_only_fields = ["project"]


class ProjectMembershipCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "project", "user_id", "role", "created_at", "updated_at"]
        read_only_fields = ["id", "project", "created_at", "updated_at"]

    def validate_user_id(self, value: int) -> int:
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User not found.")
        return value


class TaskSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)
    assignee = UserPublicSerializer(read_only=True)
    assignee_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "title",
            "description",
            "status",
            "priority",
            "created_by",
            "assignee",
            "assignee_id",
            "due_date",
            "start_date",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["project", "created_by", "assignee", "completed_at", "created_at", "updated_at"]

    def validate_assignee_id(self, value: int | None) -> int | None:
        if value is None:
            return None
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("Assignee user not found.")
        return value


class CommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "task", "author", "body", "created_at", "updated_at"]
        read_only_fields = ["task", "author", "created_at", "updated_at"]


class ActivityLogSerializer(serializers.ModelSerializer):
    actor = UserPublicSerializer(read_only=True)

    class Meta:
        model = ActivityLog
        fields = ["id", "actor", "event_type", "message", "team", "project", "task", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]


class AIPrioritySuggestRequestSerializer(serializers.Serializer):
    """AI baseline: suggest a priority for a task."""
    task_id = serializers.IntegerField()
    title = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True)


class AIPrioritySuggestResponseSerializer(serializers.Serializer):
    suggested_priority = serializers.ChoiceField(choices=Task.Priority.choices)
    rationale = serializers.CharField()


class AIDelayRiskRequestSerializer(serializers.Serializer):
    """AI baseline: predict delay risk for a task."""
    task_id = serializers.IntegerField()
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.IntegerField(required=False)
    has_assignee = serializers.BooleanField(required=False)


class AIDelayRiskResponseSerializer(serializers.Serializer):
    risk_score = serializers.FloatField(min_value=0.0, max_value=1.0)
    risk_level = serializers.ChoiceField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")])
    explanation = serializers.CharField()
