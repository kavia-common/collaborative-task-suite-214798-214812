from __future__ import annotations

import django_filters
from django.db.models import Q

from .models import ActivityLog, Comment, Project, Task, Team


class TeamFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

    class Meta:
        model = Team
        fields = ["q"]


class ProjectFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

    class Meta:
        model = Project
        fields = ["q"]


class TaskFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    priority = django_filters.NumberFilter(field_name="priority", lookup_expr="exact")
    assignee = django_filters.NumberFilter(field_name="assignee_id", lookup_expr="exact")
    due_before = django_filters.IsoDateTimeFilter(field_name="due_date", lookup_expr="lte")
    due_after = django_filters.IsoDateTimeFilter(field_name="due_date", lookup_expr="gte")
    q = django_filters.CharFilter(method="filter_q")

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value))

    class Meta:
        model = Task
        fields = ["status", "priority", "assignee", "due_before", "due_after", "q"]


class CommentFilter(django_filters.FilterSet):
    class Meta:
        model = Comment
        fields = ["task"]


class ActivityLogFilter(django_filters.FilterSet):
    class Meta:
        model = ActivityLog
        fields = ["team", "project", "task", "event_type"]
