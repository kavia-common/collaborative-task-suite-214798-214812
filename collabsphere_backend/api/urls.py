from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AIViewSet, ActivityLogViewSet, AuthViewSet, ProjectViewSet, TaskViewSet, TeamViewSet, health

router = DefaultRouter()
router.register(r"auth", AuthViewSet, basename="auth")
router.register(r"teams", TeamViewSet, basename="teams")
router.register(r"activity", ActivityLogViewSet, basename="activity")
router.register(r"ai", AIViewSet, basename="ai")

# Nested-ish routes (lightweight, explicit) to avoid adding extra dependencies
team_projects = ProjectViewSet.as_view({"get": "list", "post": "create"})
team_project_detail = ProjectViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
team_project_members = ProjectViewSet.as_view({"get": "members", "post": "add_member"})

project_tasks = TaskViewSet.as_view({"get": "list", "post": "create"})
project_task_detail = TaskViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
task_comments = TaskViewSet.as_view({"get": "comments", "post": "add_comment"})

urlpatterns = [
    path("health/", health, name="Health"),
    path("", include(router.urls)),
    # Teams -> Projects
    path("teams/<int:team_pk>/projects/", team_projects, name="team-projects"),
    path("teams/<int:team_pk>/projects/<int:pk>/", team_project_detail, name="team-project-detail"),
    path("teams/<int:team_pk>/projects/<int:pk>/members/", team_project_members, name="project-members"),
    # Projects -> Tasks
    path("projects/<int:project_pk>/tasks/", project_tasks, name="project-tasks"),
    path("projects/<int:project_pk>/tasks/<int:pk>/", project_task_detail, name="project-task-detail"),
    path("projects/<int:project_pk>/tasks/<int:pk>/comments/", task_comments, name="task-comments"),
]
