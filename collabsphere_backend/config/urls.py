"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]

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
    permission_classes=(permissions.AllowAny,),
)


def get_full_url(request):
    scheme = request.scheme
    host = request.get_host()
    forwarded_port = request.META.get("HTTP_X_FORWARDED_PORT")

    if ":" not in host and forwarded_port:
        host = f"{host}:{forwarded_port}"

    return f"{scheme}://{host}"


@csrf_exempt
def dynamic_schema_view(request, *args, **kwargs):
    url = get_full_url(request)
    view = get_schema_view(
        openapi.Info(
            title="CollabSphere API",
            default_version="v1",
            description="Interactive Swagger docs for CollabSphere API.",
        ),
        public=True,
        url=url,
        permission_classes=(permissions.AllowAny,),
    )
    return view.with_ui("swagger", cache_timeout=0)(request)


urlpatterns += [
    re_path(r"^docs/$", dynamic_schema_view, name="schema-swagger-ui"),
    re_path(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    re_path(r"^swagger\.json$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
]
