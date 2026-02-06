from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .filters import ActivityLogFilter, ProjectFilter, TaskFilter, TeamFilter
from .models import (
    ActivityLog,
    Comment,
    Project,
    ProjectMembership,
    Task,
    Team,
    TeamMembership,
)
from .permissions import (
    IsAuthenticatedAndProjectManager,
    IsAuthenticatedAndProjectMember,
    IsAuthenticatedAndTeamAdmin,
    IsAuthenticatedAndTeamMember,
)
from .serializers import (
    AIDelayRiskRequestSerializer,
    AIDelayRiskResponseSerializer,
    AIPrioritySuggestRequestSerializer,
    AIPrioritySuggestResponseSerializer,
    ActivityLogSerializer,
    CommentSerializer,
    LoginSerializer,
    ProjectMembershipCreateSerializer,
    ProjectMembershipSerializer,
    ProjectSerializer,
    RegisterSerializer,
    TaskSerializer,
    TeamMembershipCreateSerializer,
    TeamMembershipSerializer,
    TeamSerializer,
    UserPublicSerializer,
)
from .services import create_activity_log

logger = logging.getLogger(__name__)
User = get_user_model()


@swagger_auto_schema(method="get", operation_summary="Health check", tags=["health"])
@api_view(["GET"])
@permission_classes([AllowAny])
# PUBLIC_INTERFACE
def health(request):
    """Simple health check endpoint."""
    return Response({"message": "Server is up!"})


class AuthViewSet(viewsets.ViewSet):
    """Authentication endpoints: register, login, token refresh via JWT."""

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={201: UserPublicSerializer, 400: "Validation error"},
        operation_summary="Register user",
        tags=["auth"],
    )
    @action(detail=False, methods=["post"], url_path="register")
    # PUBLIC_INTERFACE
    def register(self, request):
        """Register a new user and return JWT tokens."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        if User.objects.filter(username=username).exists():
            raise ValidationError({"username": "Username already exists."})
        if User.objects.filter(email=email).exists():
            raise ValidationError({"email": "Email already exists."})

        user = User.objects.create_user(username=username, email=email, password=password)
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserPublicSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: "Tokens", 401: "Invalid credentials"},
        operation_summary="Login user",
        tags=["auth"],
    )
    @action(detail=False, methods=["post"], url_path="login")
    # PUBLIC_INTERFACE
    def login(self, request):
        """Login with username/password and return JWT tokens."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if not user:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserPublicSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        )


class TeamViewSet(viewsets.ModelViewSet):
    """Teams CRUD. Listing returns only teams user is a member of."""

    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TeamFilter
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Team.objects.filter(memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        with transaction.atomic():
            team = serializer.save(created_by=self.request.user)
            TeamMembership.objects.create(team=team, user=self.request.user, role=TeamMembership.Role.OWNER)
            create_activity_log(
                actor=self.request.user,
                event_type=ActivityLog.EventType.TEAM_CREATED,
                team=team,
                message=f"Team created: {team.name}",
            )

    @swagger_auto_schema(operation_summary="List team members", tags=["teams"])
    @action(detail=True, methods=["get"], url_path="members", permission_classes=[IsAuthenticatedAndTeamMember])
    # PUBLIC_INTERFACE
    def members(self, request, pk=None):
        """List memberships for a team."""
        memberships = TeamMembership.objects.filter(team_id=pk).select_related("user").order_by("created_at")
        return Response(TeamMembershipSerializer(memberships, many=True).data)

    @swagger_auto_schema(
        request_body=TeamMembershipCreateSerializer,
        operation_summary="Add team member",
        tags=["teams"],
    )
    @action(detail=True, methods=["post"], url_path="members", permission_classes=[IsAuthenticatedAndTeamAdmin])
    # PUBLIC_INTERFACE
    def add_member(self, request, pk=None):
        """Add a user to the team (admin/owner only)."""
        serializer = TeamMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.get(id=serializer.validated_data["user_id"])
        role = serializer.validated_data.get("role", TeamMembership.Role.MEMBER)
        try:
            membership = TeamMembership.objects.create(team_id=pk, user=user, role=role)
        except IntegrityError:
            raise ValidationError({"detail": "User is already a member of this team."})

        create_activity_log(
            actor=request.user,
            event_type=ActivityLog.EventType.TEAM_MEMBER_ADDED,
            team_id=int(pk),
            message=f"Added user {user.id} to team",
            metadata={"user_id": user.id, "role": role},
        )
        return Response(TeamMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class ProjectViewSet(viewsets.ModelViewSet):
    """Projects CRUD scoped to a team. Uses nested URL /teams/{team_pk}/projects/"""

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticatedAndTeamMember]
    filterset_class = ProjectFilter
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        team_pk = self.kwargs.get("team_pk")
        return Project.objects.filter(team_id=team_pk, team__memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        team_pk = self.kwargs.get("team_pk")
        with transaction.atomic():
            project = serializer.save(team_id=team_pk, created_by=self.request.user)
            ProjectMembership.objects.create(project=project, user=self.request.user, role=ProjectMembership.Role.MANAGER)
            create_activity_log(
                actor=self.request.user,
                event_type=ActivityLog.EventType.PROJECT_CREATED,
                team_id=int(team_pk),
                project=project,
                message=f"Project created: {project.name}",
            )

    @swagger_auto_schema(operation_summary="List project members", tags=["projects"])
    @action(detail=True, methods=["get"], url_path="members", permission_classes=[IsAuthenticatedAndProjectMember])
    # PUBLIC_INTERFACE
    def members(self, request, team_pk=None, pk=None):
        """List memberships for a project."""
        memberships = ProjectMembership.objects.filter(project_id=pk).select_related("user").order_by("created_at")
        return Response(ProjectMembershipSerializer(memberships, many=True).data)

    @swagger_auto_schema(
        request_body=ProjectMembershipCreateSerializer,
        operation_summary="Add project member",
        tags=["projects"],
    )
    @action(detail=True, methods=["post"], url_path="members", permission_classes=[IsAuthenticatedAndProjectManager])
    # PUBLIC_INTERFACE
    def add_member(self, request, team_pk=None, pk=None):
        """Add a user to the project (project manager or team admin/owner)."""
        serializer = ProjectMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.get(id=serializer.validated_data["user_id"])
        role = serializer.validated_data.get("role", ProjectMembership.Role.CONTRIBUTOR)

        # Ensure user is a team member as well
        if not TeamMembership.objects.filter(team_id=team_pk, user=user).exists():
            raise ValidationError({"detail": "User must be a member of the team before joining project."})

        try:
            membership = ProjectMembership.objects.create(project_id=pk, user=user, role=role)
        except IntegrityError:
            raise ValidationError({"detail": "User is already a member of this project."})

        create_activity_log(
            actor=request.user,
            event_type=ActivityLog.EventType.PROJECT_MEMBER_ADDED,
            team_id=int(team_pk),
            project_id=int(pk),
            message=f"Added user {user.id} to project",
            metadata={"user_id": user.id, "role": role},
        )
        return Response(ProjectMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class TaskViewSet(viewsets.ModelViewSet):
    """Tasks CRUD scoped to a project. Nested URL /projects/{project_pk}/tasks/"""

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticatedAndProjectMember]
    filterset_class = TaskFilter
    ordering_fields = ["created_at", "due_date", "priority", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        project_pk = self.kwargs.get("project_pk")
        return Task.objects.filter(project_id=project_pk, project__memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        project_pk = self.kwargs.get("project_pk")
        assignee_id = serializer.validated_data.pop("assignee_id", None)
        assignee = User.objects.filter(id=assignee_id).first() if assignee_id else None

        if assignee and not ProjectMembership.objects.filter(project_id=project_pk, user=assignee).exists():
            raise ValidationError({"assignee_id": "Assignee must be a member of the project."})

        task = serializer.save(project_id=project_pk, created_by=self.request.user, assignee=assignee)
        create_activity_log(
            actor=self.request.user,
            event_type=ActivityLog.EventType.TASK_CREATED,
            project_id=int(project_pk),
            task=task,
            message=f"Task created: {task.title}",
        )

    def perform_update(self, serializer):
        # Track status change
        old_task: Task = self.get_object()
        old_status = old_task.status

        assignee_id = serializer.validated_data.pop("assignee_id", None) if "assignee_id" in serializer.validated_data else None
        assignee = None
        if "assignee_id" in serializer.validated_data or assignee_id is not None:
            if assignee_id is None:
                assignee = None
            else:
                assignee = User.objects.filter(id=assignee_id).first()
                if not assignee:
                    raise ValidationError({"assignee_id": "Assignee user not found."})
                if not ProjectMembership.objects.filter(project=old_task.project, user=assignee).exists():
                    raise ValidationError({"assignee_id": "Assignee must be a member of the project."})

        task = serializer.save(assignee=assignee if "assignee_id" in serializer.validated_data else old_task.assignee)

        create_activity_log(
            actor=self.request.user,
            event_type=ActivityLog.EventType.TASK_UPDATED,
            project=task.project,
            task=task,
            message="Task updated",
            metadata={"fields": list(serializer.validated_data.keys())},
        )

        if old_status != task.status:
            if task.status == Task.Status.DONE and not task.completed_at:
                task.completed_at = timezone.now()
                task.save(update_fields=["completed_at"])

            create_activity_log(
                actor=self.request.user,
                event_type=ActivityLog.EventType.TASK_STATUS_CHANGED,
                project=task.project,
                task=task,
                message=f"Status changed {old_status} -> {task.status}",
            )

    @swagger_auto_schema(operation_summary="List task comments", tags=["comments"])
    @action(detail=True, methods=["get"], url_path="comments")
    # PUBLIC_INTERFACE
    def comments(self, request, project_pk=None, pk=None):
        """List comments for a task."""
        task = self.get_object()
        comments = Comment.objects.filter(task=task).select_related("author").order_by("created_at")
        return Response(CommentSerializer(comments, many=True).data)

    @swagger_auto_schema(
        request_body=CommentSerializer,
        operation_summary="Add task comment",
        tags=["comments"],
    )
    @action(detail=True, methods=["post"], url_path="comments")
    # PUBLIC_INTERFACE
    def add_comment(self, request, project_pk=None, pk=None):
        """Create a comment for a task."""
        task = self.get_object()
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = Comment.objects.create(task=task, author=request.user, body=serializer.validated_data["body"])
        create_activity_log(
            actor=request.user,
            event_type=ActivityLog.EventType.TASK_COMMENTED,
            project=task.project,
            task=task,
            message="Comment added",
            metadata={"comment_id": comment.id},
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class ActivityLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only activity log endpoint filtered by team/project/task, only for members."""

    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = ActivityLogFilter
    ordering_fields = ["created_at", "event_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Only logs related to teams the user belongs to
        return ActivityLog.objects.filter(team__memberships__user=self.request.user).distinct()


class AIViewSet(viewsets.ViewSet):
    """Baseline AI endpoints (non-ML heuristics) for priority suggestion and delay-risk prediction."""

    permission_classes = [IsAuthenticated]

    def _get_task_for_user(self, request, task_id: int) -> Task:
        task = Task.objects.select_related("project", "project__team").filter(id=task_id).first()
        if not task:
            raise ValidationError({"task_id": "Task not found."})

        if not ProjectMembership.objects.filter(project=task.project, user=request.user).exists():
            raise PermissionDenied("You must be a project member to use AI features on this task.")
        return task

    @swagger_auto_schema(
        request_body=AIPrioritySuggestRequestSerializer,
        responses={200: AIPrioritySuggestResponseSerializer},
        operation_summary="Suggest task priority (baseline AI)",
        tags=["ai"],
    )
    @action(detail=False, methods=["post"], url_path="priority-suggest")
    # PUBLIC_INTERFACE
    def priority_suggest(self, request):
        """Suggest a priority based on due date proximity, status, and keyword heuristics."""
        serializer = AIPrioritySuggestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = self._get_task_for_user(request, serializer.validated_data["task_id"])
        due_date = serializer.validated_data.get("due_date") or task.due_date
        title = serializer.validated_data.get("title") or task.title or ""
        description = serializer.validated_data.get("description") or task.description or ""
        status_val = (serializer.validated_data.get("status") or task.status or "").lower()

        now = timezone.now()
        rationale_parts: list[str] = []

        suggested = Task.Priority.MEDIUM

        urgent_keywords = ["urgent", "asap", "blocker", "critical", "p0"]
        high_keywords = ["important", "deadline", "risk", "customer", "incident"]

        text = f"{title}\n{description}".lower()
        if any(k in text for k in urgent_keywords):
            suggested = Task.Priority.URGENT
            rationale_parts.append("Detected urgency keywords.")
        elif any(k in text for k in high_keywords):
            suggested = Task.Priority.HIGH
            rationale_parts.append("Detected high-impact keywords.")

        if due_date:
            delta = due_date - now
            if delta <= timedelta(days=1):
                suggested = max(suggested, Task.Priority.URGENT)
                rationale_parts.append("Due within 24 hours.")
            elif delta <= timedelta(days=3):
                suggested = max(suggested, Task.Priority.HIGH)
                rationale_parts.append("Due within 3 days.")
            elif delta <= timedelta(days=7):
                suggested = max(suggested, Task.Priority.MEDIUM)
                rationale_parts.append("Due within 7 days.")

        if status_val in {Task.Status.BLOCKED, "blocked"}:
            suggested = max(suggested, Task.Priority.HIGH)
            rationale_parts.append("Task is blocked.")
        if status_val in {Task.Status.DONE, "done"}:
            suggested = Task.Priority.LOW
            rationale_parts.append("Task is done; low priority.")

        rationale = " ".join(rationale_parts) if rationale_parts else "Baseline heuristic: default medium priority."
        create_activity_log(
            actor=request.user,
            event_type=ActivityLog.EventType.AI_PRIORITY_SUGGESTED,
            team=task.project.team,
            project=task.project,
            task=task,
            message="AI suggested priority",
            metadata={"suggested_priority": int(suggested)},
        )
        return Response({"suggested_priority": suggested, "rationale": rationale})

    @swagger_auto_schema(
        request_body=AIDelayRiskRequestSerializer,
        responses={200: AIDelayRiskResponseSerializer},
        operation_summary="Predict delay risk (baseline AI)",
        tags=["ai"],
    )
    @action(detail=False, methods=["post"], url_path="delay-risk")
    # PUBLIC_INTERFACE
    def delay_risk(self, request):
        """Predict delay risk using simple heuristics: due date proximity, status, assignee."""
        serializer = AIDelayRiskRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = self._get_task_for_user(request, serializer.validated_data["task_id"])
        due_date = serializer.validated_data.get("due_date") or task.due_date
        status_val = (serializer.validated_data.get("status") or task.status or "").lower()
        priority_val = serializer.validated_data.get("priority") or task.priority
        has_assignee = serializer.validated_data.get("has_assignee")
        if has_assignee is None:
            has_assignee = bool(task.assignee_id)

        now = timezone.now()
        risk = 0.15  # baseline

        if not has_assignee:
            risk += 0.25

        if status_val in {Task.Status.TODO, "todo"}:
            risk += 0.10
        if status_val in {Task.Status.BLOCKED, "blocked"}:
            risk += 0.35
        if status_val in {Task.Status.DONE, "done"}:
            risk = 0.0

        if priority_val in {Task.Priority.URGENT, Task.Priority.HIGH}:
            risk += 0.10

        if due_date:
            delta = due_date - now
            if delta.total_seconds() < 0:
                risk += 0.35  # overdue
            elif delta <= timedelta(days=1):
                risk += 0.25
            elif delta <= timedelta(days=3):
                risk += 0.15
            elif delta <= timedelta(days=7):
                risk += 0.05

        risk = max(0.0, min(1.0, float(risk)))

        if risk >= 0.67:
            level = "high"
        elif risk >= 0.34:
            level = "medium"
        else:
            level = "low"

        explanation = (
            "Baseline heuristic model using due date proximity, status, assignee presence, and priority."
        )

        create_activity_log(
            actor=request.user,
            event_type=ActivityLog.EventType.AI_DELAY_RISK_PREDICTED,
            team=task.project.team,
            project=task.project,
            task=task,
            message="AI predicted delay risk",
            metadata={"risk_score": risk, "risk_level": level},
        )
        return Response({"risk_score": risk, "risk_level": level, "explanation": explanation})
