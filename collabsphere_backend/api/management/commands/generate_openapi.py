import json
import os

from django.core.management.base import BaseCommand
from django.test import RequestFactory
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny


class Command(BaseCommand):
    def handle(self, *args, **options):
        """
        Generate and persist an OpenAPI/Swagger spec for the running Django project.

        This is used by CI/automation to publish an API interface snapshot under:
        collabsphere_backend/interfaces/openapi.json
        """
        factory = RequestFactory()

        # Request path doesn't have to match a real URL; drf-yasg uses the request
        # to determine host/scheme and to build the basePath.
        django_request = factory.get("/swagger.json")

        schema_view = get_schema_view(
            openapi.Info(
                title="CollabSphere API",
                default_version="v1",
                description=(
                    "CollabSphere is an AI-assisted team collaboration and task management platform.\n\n"
                    "Auth: Use JWT. Obtain tokens via /api/auth/login/ or /api/auth/register/ and pass:\n"
                    "Authorization: Bearer <access_token>"
                ),
            ),
            public=True,
            permission_classes=(AllowAny,),
        )

        # Call the view with the raw Django HttpRequest.
        response = schema_view.without_ui(cache_timeout=0)(django_request)
        response.render()

        openapi_schema = json.loads(response.content.decode())

        # Write to the backend container's interfaces/ folder (repo-relative when running manage.py).
        output_dir = "interfaces"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "openapi.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(openapi_schema, f, indent=2, sort_keys=True)
