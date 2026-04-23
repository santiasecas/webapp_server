"""
Tickets App — Internal Issue Tracker
======================================
Segunda app de ejemplo que demuestra:
  - Campos con enum (status, priority)
  - Filtros múltiples en listado
  - Relación entre datos (asignado a usuario htpasswd)
  - Misma arquitectura, diferente dominio
"""
from fastapi import FastAPI

from core.registry import AppRegistry

tickets_app = FastAPI(title="Tickets App")

from apps.tickets_app.routers import tickets  # noqa: E402

tickets_app.include_router(tickets.router)

AppRegistry.register(
    name="tickets_app",
    router=tickets_app,
    prefix="/apps/tickets",
    description="Registro de incidencias y tareas internas",
    icon="🎫",
    category="Operations",
    permission_required=True,   # Users need explicit access granted by an admin
)

app_module = tickets_app
