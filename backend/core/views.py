from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    responses=inline_serializer(
        "Health", {"status": serializers.CharField(), "database": serializers.CharField()}
    )
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness and database check, for Docker and Kubernetes probes. Never needs a login."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database = "ok"
    except Exception:  # noqa: BLE001 - any database error means "not ready"
        database = "unavailable"
    status = 200 if database == "ok" else 503
    return Response({"status": "ok" if status == 200 else "degraded", "database": database}, status=status)
