"""
URL configuration for zoea project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/dev/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from ninja import NinjaAPI

from accounts.api import router as auth_router
from agents.api import router as agents_router
from chat.api import router as chat_router
from context_clipboards.api import router as clipboards_router
from document_rag.api import router as rag_router
from documents.api import router as documents_router
from documents.notebook_api import router as notebooks_router
from email_gateway.api import router as email_router
from flows.api import router as flows_router
from llm_providers.api import router as llm_router
from projects.api import router as projects_router
from workspaces.api import router as workspaces_router
from workflows.api import router as workflows_router
from events.api import router as events_router
from zoea.system_api import router as system_router

api = NinjaAPI(title="Zoea Collab: Agent Toolkit API", version="0.1.0")
api.add_router("/", chat_router, tags=["chat"])
api.add_router("/auth", auth_router, tags=["auth"])
api.add_router("/clipboards", clipboards_router, tags=["clipboards"])
api.add_router("/notebooks", notebooks_router, tags=["notebooks"])
api.add_router("/", documents_router, tags=["documents"])
api.add_router("/llm", llm_router, tags=["llm"])
api.add_router("/", projects_router, tags=["projects"])
api.add_router("/", workspaces_router, tags=["workspaces"])
api.add_router("/system", system_router, tags=["system"])
api.add_router("/email", email_router, tags=["email"])
api.add_router("/rag", rag_router, tags=["document-rag"])
api.add_router("/flows", flows_router, tags=["flows"])
api.add_router("/workflows", workflows_router, tags=["workflows"])
api.add_router("/events", events_router, tags=["events"])
api.add_router("/agents", agents_router, tags=["agents"])

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("accounts/", include("allauth.account.urls")),  # django-allauth registration URLs
]

# Serve media files in development or when SERVE_MEDIA is set
# This allows serving media files on development VMs even with DEBUG=False
import os
if settings.DEBUG or os.getenv("SERVE_MEDIA", "False") == "True":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
