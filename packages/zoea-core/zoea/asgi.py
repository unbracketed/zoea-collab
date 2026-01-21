"""
ASGI configuration for Zoea Collab: Agent Cowork Toolkit.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/stable/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zoea.settings")

# Get the Django ASGI application first
django_asgi_app = get_asgi_application()

# Conditionally mount media file serving for development
# This is needed because Django's static() doesn't work with ASGI
if os.getenv("SERVE_MEDIA", "False") == "True":
    from starlette.staticfiles import StaticFiles
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount
    from starlette.applications import Starlette
    from django.conf import settings

    # Create a Starlette app that mounts media files with CORS support
    media_app = Starlette(
        routes=[
            Mount("/media", app=StaticFiles(directory=str(settings.MEDIA_ROOT)), name="media"),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Allow all origins for media files
                allow_methods=["GET", "HEAD", "OPTIONS"],
                allow_headers=["*"],
            ),
        ],
    )

    # Use Django for all non-media routes
    async def app(scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/media/"):
            await media_app(scope, receive, send)
        else:
            await django_asgi_app(scope, receive, send)

    application = app
else:
    application = django_asgi_app
    app = application
