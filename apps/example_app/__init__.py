"""
Example App - Contacts/Records Management
==========================================
Demonstrates:
  - HTML form with Jinja2 template
  - PostgreSQL persistence via SQLAlchemy
  - Protected routes with Basic Auth
  - Repository pattern
  - Pydantic validation
"""
from fastapi import FastAPI

from core.registry import AppRegistry

# Create sub-application
example_app = FastAPI(title="Example App - Contacts")

# Import router (must happen after example_app is created)
from apps.example_app.routers import contacts  # noqa: E402

example_app.include_router(contacts.router)

# Register with platform
AppRegistry.register(
    name="example_app",
    router=example_app,
    prefix="/apps/contacts",
    description="Contact registry — example of form + DB + auth",
    icon="👤",
    category="Examples",
)

# Expose as app_module for import in main.py
app_module = example_app
