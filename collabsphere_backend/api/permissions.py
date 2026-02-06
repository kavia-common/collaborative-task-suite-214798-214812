from __future__ import annotations

from dataclasses import dataclass

from rest_framework.permissions import BasePermission

from .models import Project, ProjectMembership, Team, TeamMembership


@dataclass(frozen=True)
class MembershipInfo:
    is_member: bool
    role: str | None


def _team_membership(user, team_id: int) -> MembershipInfo:
    if not user or not user.is_authenticated:
        return MembershipInfo(False, None)
    m = TeamMembership.objects.filter(team_id=team_id, user=user).only("role").first()
    if not m:
        return MembershipInfo(False, None)
    return MembershipInfo(True, m.role)


def _project_membership(user, project_id: int) -> MembershipInfo:
    if not user or not user.is_authenticated:
        return MembershipInfo(False, None)
    m = ProjectMembership.objects.filter(project_id=project_id, user=user).only("role").first()
    if not m:
        return MembershipInfo(False, None)
    return MembershipInfo(True, m.role)


class IsAuthenticatedAndTeamMember(BasePermission):
    """Allows access only to authenticated users who are members of the team."""

    message = "You must be a member of this team."

    def has_permission(self, request, view) -> bool:
        team_id = (
            view.kwargs.get("team_pk")
            or request.query_params.get("team")
            or request.data.get("team")
            or request.data.get("team_id")
        )
        if not team_id:
            # For list/create of teams, allow authenticated; object-level will handle detail.
            return bool(request.user and request.user.is_authenticated)
        try:
            team_id_int = int(team_id)
        except (TypeError, ValueError):
            return False
        return _team_membership(request.user, team_id_int).is_member

    def has_object_permission(self, request, view, obj) -> bool:
        team_id = obj.id if isinstance(obj, Team) else getattr(obj, "team_id", None)
        if not team_id:
            return False
        return _team_membership(request.user, int(team_id)).is_member


class IsAuthenticatedAndTeamAdmin(BasePermission):
    """Allows access only to team owners/admins."""

    message = "You must be a team admin/owner."

    def has_permission(self, request, view) -> bool:
        team_id = view.kwargs.get("team_pk") or request.data.get("team") or request.data.get("team_id")
        if not team_id:
            return False
        try:
            team_id_int = int(team_id)
        except (TypeError, ValueError):
            return False
        info = _team_membership(request.user, team_id_int)
        return info.is_member and info.role in {TeamMembership.Role.OWNER, TeamMembership.Role.ADMIN}


class IsAuthenticatedAndProjectMember(BasePermission):
    """Allows access only to authenticated users who are members of the project."""

    message = "You must be a member of this project."

    def has_permission(self, request, view) -> bool:
        project_id = (
            view.kwargs.get("project_pk")
            or request.query_params.get("project")
            or request.data.get("project")
            or request.data.get("project_id")
        )
        if not project_id:
            return bool(request.user and request.user.is_authenticated)
        try:
            project_id_int = int(project_id)
        except (TypeError, ValueError):
            return False
        return _project_membership(request.user, project_id_int).is_member

    def has_object_permission(self, request, view, obj) -> bool:
        if isinstance(obj, Project):
            project_id = obj.id
        else:
            project_id = getattr(obj, "project_id", None)
        if not project_id:
            return False
        return _project_membership(request.user, int(project_id)).is_member


class IsAuthenticatedAndProjectManager(BasePermission):
    """Allows access only to project managers (or higher at team level)."""

    message = "You must be a project manager."

    def has_permission(self, request, view) -> bool:
        project_id = view.kwargs.get("project_pk") or request.data.get("project") or request.data.get("project_id")
        if not project_id:
            return False
        try:
            project_id_int = int(project_id)
        except (TypeError, ValueError):
            return False
        info = _project_membership(request.user, project_id_int)
        if info.is_member and info.role == ProjectMembership.Role.MANAGER:
            return True

        # Fallback: allow team admin/owner for the owning team
        project = Project.objects.filter(id=project_id_int).only("team_id").first()
        if not project:
            return False
        team_info = _team_membership(request.user, project.team_id)
        return team_info.is_member and team_info.role in {TeamMembership.Role.OWNER, TeamMembership.Role.ADMIN}
