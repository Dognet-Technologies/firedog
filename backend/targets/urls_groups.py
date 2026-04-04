"""
URL Configuration per Target Groups
AGGIUNGI QUESTO a: backend/targets/urls.py

Oppure crea un nuovo file: backend/targets/urls_groups.py
e poi importalo nel main urls.py
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_groups import TargetGroupViewSet, GroupRuleTemplateViewSet

router = DefaultRouter()
router.register(r"groups", TargetGroupViewSet, basename="targetgroup")
router.register(r"group-rules", GroupRuleTemplateViewSet, basename="grouprule")

urlpatterns = [
    path("", include(router.urls)),
]

# Nel file backend/firedog/urls.py, aggiungi:
# path('api/', include('targets.urls_groups')),
