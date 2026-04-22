#!/usr/bin/env python3
"""
scripts/new_app.py — Scaffold a new webapp module.

Usage:
    python scripts/new_app.py my_app --prefix /apps/my-app --description "My App"

Generates:
    apps/my_app/__init__.py
    apps/my_app/models.py
    apps/my_app/schemas.py
    apps/my_app/repositories/__init__.py
    apps/my_app/repositories/item_repository.py
    apps/my_app/services/__init__.py
    apps/my_app/services/item_service.py
    apps/my_app/routers/__init__.py
    apps/my_app/routers/items.py
    templates/my_app/item_list.html
    templates/my_app/item_form.html
"""
import argparse
import os
import sys
import textwrap
from pathlib import Path


def snake_to_title(s: str) -> str:
    return s.replace("_", " ").title()


def write(path: Path, content: str, dry_run: bool = False):
    if dry_run:
        print(f"  [DRY RUN] Would create: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"  Skipping (exists): {path}")
        return
    path.write_text(textwrap.dedent(content).lstrip())
    print(f"  Created: {path}")


def scaffold(name: str, prefix: str, description: str, icon: str, dry_run: bool):
    base = Path("apps") / name
    tmpl = Path("templates") / name
    title = snake_to_title(name)

    files = {
        base / "__init__.py": f'''\
            """
            {title} App
            """
            from fastapi import FastAPI
            from core.registry import AppRegistry

            {name}_app = FastAPI(title="{title}")

            from apps.{name}.routers import items  # noqa
            {name}_app.include_router(items.router)

            AppRegistry.register(
                name="{name}",
                router={name}_app,
                prefix="{prefix}",
                description="{description}",
                icon="{icon}",
                category="Apps",
            )

            app_module = {name}_app
            ''',

        base / "models.py": f'''\
            """
            {title} — SQLAlchemy models.
            """
            from datetime import datetime
            from sqlalchemy import DateTime, Integer, String, func
            from sqlalchemy.orm import Mapped, mapped_column
            from core.database import Base


            class Item(Base):
                __tablename__ = "{name}_items"

                id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
                name: Mapped[str] = mapped_column(String(200), nullable=False)
                created_at: Mapped[datetime] = mapped_column(
                    DateTime(timezone=True), server_default=func.now()
                )
            ''',

        base / "schemas.py": f'''\
            """
            {title} — Pydantic schemas.
            """
            from datetime import datetime
            from pydantic import BaseModel, Field


            class ItemCreate(BaseModel):
                name: str = Field(..., min_length=1, max_length=200)


            class ItemRead(ItemCreate):
                id: int
                created_at: datetime
                model_config = {{"from_attributes": True}}
            ''',

        base / "repositories" / "__init__.py": "from apps.{name}.repositories.item_repository import ItemRepository\n__all__ = ['ItemRepository']".format(name=name),

        base / "repositories" / "item_repository.py": f'''\
            """
            {title} — Item repository.
            """
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import AsyncSession
            from apps.{name}.models import Item
            from apps.{name}.schemas import ItemCreate


            class ItemRepository:
                def __init__(self, db: AsyncSession):
                    self.db = db

                async def get_all(self) -> list[Item]:
                    r = await self.db.execute(select(Item).order_by(Item.created_at.desc()))
                    return list(r.scalars().all())

                async def create(self, data: ItemCreate) -> Item:
                    item = Item(**data.model_dump())
                    self.db.add(item)
                    await self.db.flush()
                    await self.db.refresh(item)
                    return item
            ''',

        base / "services" / "__init__.py": "from apps.{name}.services.item_service import ItemService\n__all__ = ['ItemService']".format(name=name),

        base / "services" / "item_service.py": f'''\
            """
            {title} — Item service.
            """
            from sqlalchemy.ext.asyncio import AsyncSession
            from apps.{name}.repositories import ItemRepository
            from apps.{name}.schemas import ItemCreate, ItemRead


            class ItemService:
                def __init__(self, db: AsyncSession):
                    self.repo = ItemRepository(db)

                async def list_items(self) -> list[ItemRead]:
                    items = await self.repo.get_all()
                    return [ItemRead.model_validate(i) for i in items]

                async def create_item(self, data: ItemCreate) -> ItemRead:
                    item = await self.repo.create(data)
                    return ItemRead.model_validate(item)
            ''',

        base / "routers" / "__init__.py": "from apps.{name}.routers import items\n__all__ = ['items']".format(name=name),

        base / "routers" / "items.py": f'''\
            """
            {title} — Items router.
            """
            from typing import Annotated
            from fastapi import APIRouter, Depends, Form, Request, status
            from fastapi.responses import HTMLResponse, RedirectResponse
            from sqlalchemy.ext.asyncio import AsyncSession
            from apps.{name}.schemas import ItemCreate
            from apps.{name}.services import ItemService
            from core.auth import require_auth
            from core.database import get_db
            from core.templates import templates

            router = APIRouter()
            Auth = Annotated[str, Depends(require_auth)]


            def get_service(db: AsyncSession = Depends(get_db)) -> ItemService:
                return ItemService(db)


            @router.get("/", response_class=HTMLResponse)
            async def list_items(request: Request, username: Auth, service: ItemService = Depends(get_service)):
                items = await service.list_items()
                return templates.TemplateResponse(
                    "{name}/item_list.html",
                    {{"request": request, "username": username, "items": items, "title": "{title}"}},
                )


            @router.get("/new", response_class=HTMLResponse)
            async def new_item_form(request: Request, username: Auth):
                return templates.TemplateResponse(
                    "{name}/item_form.html",
                    {{"request": request, "username": username, "errors": {{}}, "title": "New Item",
                      "form_action": "{prefix}/new", "submit_label": "Create"}},
                )


            @router.post("/new")
            async def create_item(
                request: Request, username: Auth, service: ItemService = Depends(get_service),
                name: str = Form(...),
            ):
                await service.create_item(ItemCreate(name=name))
                return RedirectResponse(url="{prefix}/?created=1", status_code=status.HTTP_303_SEE_OTHER)
            ''',

        tmpl / "item_list.html": f'''\
            {{% extends "base/layout.html" %}}
            {{% block header_title %}}{title}{{% endblock %}}
            {{% block header_actions %}}<a href="{prefix}/new" class="btn btn-primary">+ New</a>{{% endblock %}}

            {{% block content %}}
            {{% if items %}}
            <div class="table-wrapper">
              <table class="data-table">
                <thead><tr><th>Name</th><th>Created</th></tr></thead>
                <tbody>
                  {{% for item in items %}}
                  <tr>
                    <td>{{{{ item.name }}}}</td>
                    <td class="text-muted">{{{{ item.created_at | date }}}}</td>
                  </tr>
                  {{% endfor %}}
                </tbody>
              </table>
            </div>
            {{% else %}}
            <div class="empty-state"><p>No items yet.</p><a href="{prefix}/new" class="btn btn-primary">Add first</a></div>
            {{% endif %}}
            {{% endblock %}}
            ''',

        tmpl / "item_form.html": f'''\
            {{% extends "base/layout.html" %}}
            {{% from "components/form_fields.html" import text_field, submit_row %}}
            {{% block header_title %}}{{{{ title }}}}{{% endblock %}}
            {{% block header_actions %}}<a href="{prefix}/" class="btn btn-ghost">← Back</a>{{% endblock %}}

            {{% block content %}}
            <div class="form-container">
              <form method="post" action="{{{{ form_action }}}}">
                <fieldset class="fieldset">
                  <legend class="fieldset-legend">Item Details</legend>
                  {{{{ text_field("name", "Name", required=True, error=errors.get("name")) }}}}
                </fieldset>
                {{{{ submit_row(submit_label, cancel_url="{prefix}/") }}}}
              </form>
            </div>
            {{% endblock %}}
            ''',
    }

    print(f"\n  Scaffolding app '{name}' at prefix '{prefix}'...\n")
    for path, content in files.items():
        write(path, content, dry_run)

    if not dry_run:
        print(f"""
  ✓ Done! Next steps:
  1. Register the app in main.py:
       from apps.{name} import app_module  # noqa: F401

  2. Add models to your DB (restart the server — Base.metadata.create_all runs on startup)

  3. Visit: http://localhost:8000{prefix}/
""")


def main():
    p = argparse.ArgumentParser(description="Scaffold a new Corporate Platform app")
    p.add_argument("name",        help="App name (snake_case, e.g. inventory_app)")
    p.add_argument("--prefix",    default=None,  help="URL prefix (default: /apps/<name>)")
    p.add_argument("--description", default="",   help="Short description")
    p.add_argument("--icon",      default="📦",   help="Emoji icon for dashboard")
    p.add_argument("--dry-run",   action="store_true", help="Print what would be created, don't write")
    args = p.parse_args()

    if not args.name.replace("_", "").isalnum():
        print("  Error: app name must be alphanumeric + underscores only")
        sys.exit(1)

    prefix = args.prefix or f"/apps/{args.name.replace('_', '-')}"
    scaffold(args.name, prefix, args.description, args.icon, args.dry_run)


if __name__ == "__main__":
    main()
