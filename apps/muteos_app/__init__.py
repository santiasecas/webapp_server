"""
Muteos App — Mute Report System
================================
Demonstrates:
  - HTML form for reporting mutes
  - PostgreSQL persistence via SQLAlchemy
  - Protected routes with authentication
  - Repository pattern
  - Pydantic validation
"""
from fastapi import FastAPI

from core.registry import AppRegistry

# Create sub-application
muteos_app = FastAPI(title="Muteos App - Mute Reports")

# Import router (must happen after muteos_app is created)
from apps.muteos_app.routers import muteos  # noqa: E402

muteos_app.include_router(muteos.router)

# Register with platform
AppRegistry.register(
    name="muteos_app",
    router=muteos_app,
    prefix="/apps/muteos",
    description="Mute reports — track component/ticket silences",
    icon="🔇",
    category="Operations",
)

# Expose as app_module for import in main.py
app_module = muteos_app
