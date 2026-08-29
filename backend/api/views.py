"""
API Endpoints per Frontend
File: backend/api/views.py

Log APIs (routed in firedog/urls.py). Le altre viste storiche (statistics,
threats, audit, traffic, performance) duplicavano endpoint mai instradati
e sono state rimosse: gli endpoint reali vivono in targets/threats/audit views.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
import os


class LogAPIView(APIView):
    """
    API per recuperare log
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/logs/?source=django&lines=100
        """
        source = request.query_params.get("source", "django")
        lines = int(request.query_params.get("lines", 100))

        logs_dir = settings.LOGS_DIR

        log_files = {
            "django": logs_dir / "django.log",
            "celery": logs_dir / "celery.log",
            "application": logs_dir / "application.log",
        }

        file_path = log_files.get(source)

        if not file_path or not os.path.exists(file_path):
            return Response(
                {"source": source, "logs": [], "message": "Log file not found"}
            )

        try:
            with open(file_path, "r") as f:
                all_lines = f.readlines()
                last_lines = [
                    line.strip() for line in all_lines[-lines:] if line.strip()
                ]

            return Response(
                {"source": source, "logs": last_lines, "total_lines": len(last_lines)}
            )
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class LogSourcesAPIView(APIView):
    """
    API per elencare sorgenti log disponibili
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/logs/sources/
        """
        logs_dir = settings.LOGS_DIR

        sources = []
        log_files = {
            "django": {
                "name": "Django/Daphne",
                "path": logs_dir / "django.log",
                "description": "Log del server web Django e Daphne",
            },
            "celery": {
                "name": "Celery",
                "path": logs_dir / "celery.log",
                "description": "Log dei task Celery Worker e Beat",
            },
            "application": {
                "name": "Application",
                "path": logs_dir / "application.log",
                "description": "Log generale dell'applicazione FireDog",
            },
        }

        for key, info in log_files.items():
            file_path = info["path"]
            exists = os.path.exists(file_path)
            size = os.path.getsize(file_path) if exists else 0
            sources.append(
                {
                    "id": key,
                    "name": info["name"],
                    "description": info["description"],
                    "path": str(file_path),
                    "exists": exists,
                    "size_bytes": size,
                }
            )

        return Response({"sources": sources})
