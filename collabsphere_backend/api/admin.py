from django.contrib import admin

from .models import ActivityLog, Comment, Project, ProjectMembership, Task, Team, TeamMembership


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    search_fields = ("name", "description")
    list_filter = ("created_at",)


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "team", "user", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("team__name", "user__username", "user__email")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "team", "name", "created_by", "created_at")
    search_fields = ("name", "description", "team__name")
    list_filter = ("created_at",)


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "user", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("project__name", "user__username", "user__email")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "title", "status", "priority", "assignee", "due_date", "created_at")
    search_fields = ("title", "description", "project__name")
    list_filter = ("status", "priority", "created_at")
    ordering = ("-created_at",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "author", "created_at")
    search_fields = ("body", "task__title", "author__username")
    list_filter = ("created_at",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "actor", "team", "project", "task", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("message", "actor__username")
    ordering = ("-created_at",)
