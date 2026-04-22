# Corporate Platform

Base de microservicios web interna en Python/FastAPI.  
Diseñada para entornos corporativos **sin Docker ni privilegios de administrador**.

---

## Estructura del proyecto

```
corporate_platform/
│
├── main.py                          # Entry point: monta todo
├── start.py                         # Script de arranque (wrapper uvicorn)
├── requirements.txt
├── .env.example                     # Plantilla de configuración
├── .htpasswd                        # Usuarios (generado con manage_users.py)
│
├── core/                            # Núcleo de la plataforma
│   ├── config.py                    # Settings (pydantic-settings + .env)
│   ├── database.py                  # Engine async SQLAlchemy + get_db()
│   ├── auth.py                      # Basic Auth + htpasswd
│   ├── registry.py                  # Registro de apps/módulos
│   ├── templates.py                 # Jinja2 + filtros personalizados
│   ├── middleware.py                # Logging de requests, CORS
│   ├── error_handlers.py            # Manejadores 404/500
│   └── logging_config.py           # Configuración de logging
│
├── apps/                            # Cada carpeta = una webapp enchufable
│   └── example_app/
│       ├── __init__.py              # Registra la app en el AppRegistry
│       ├── models.py                # ORM SQLAlchemy
│       ├── schemas.py               # Validación Pydantic
│       ├── repositories/            # Acceso a datos (SQL)
│       ├── services/                # Lógica de negocio
│       └── routers/                 # Rutas HTTP (FastAPI)
│
├── templates/                       # Jinja2
│   ├── base/
│   │   ├── layout.html              # Layout maestro (sidebar, header)
│   │   ├── dashboard.html           # Página de inicio
│   │   └── error.html              # Página de error genérica
│   ├── components/
│   │   ├── form_fields.html         # Macros reutilizables de formulario
│   │   └── table.html               # Macros de tabla + paginación
│   └── example_app/                 # Templates específicos de cada app
│
├── static/
│   ├── css/platform.css
│   └── js/platform.js
│
├── scripts/
│   ├── manage_users.py              # Gestión de usuarios htpasswd
│   └── new_app.py                   # Scaffolding de nuevas apps
│
└── tests/
    └── test_platform.py
```

---

## Instalación rápida

### 1. Requisitos previos

- Python 3.11+ (sin privilegios de admin)
- Acceso a PostgreSQL existente
- Conexión a internet para instalar paquetes (o `.whl` en intranet)

### 2. Crear entorno virtual e instalar dependencias

```bash
cd corporate_platform

# Crear venv local (sin sudo)
python3 -m venv .venv

# Activar
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# Instalar
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus datos:

```env
DB_HOST=tu-servidor-postgres
DB_NAME=corporate_platform
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña

# Genera una clave segura:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=pon-aqui-tu-clave-secreta

ENVIRONMENT=production
DEBUG=false
```

### 4. Crear usuarios

```bash
# Añadir el primer usuario (pedirá contraseña)
python scripts/manage_users.py add admin

# Añadir con contraseña directa (menos seguro)
python scripts/manage_users.py add otro_usuario MiPassword123

# Listar usuarios
python scripts/manage_users.py list

# Verificar contraseña
python scripts/manage_users.py verify admin

# Cambiar contraseña
python scripts/manage_users.py passwd admin
```

El archivo `.htpasswd` se crea/actualiza automáticamente.  
Las contraseñas se almacenan con **bcrypt** (compatible con Apache `htpasswd -B`).

### 5. Arrancar el servidor

```bash
# Modo desarrollo (auto-reload al modificar archivos)
python start.py --reload

# Modo producción
python start.py

# En un puerto específico
python start.py --port 9000

# Sin el script wrapper (equivalente)
uvicorn main:app --host 127.0.0.1 --port 8000
```

Abre el navegador en: **http://127.0.0.1:8000**

El navegador pedirá usuario y contraseña (Basic Auth).  
Usa las credenciales que creaste en el paso anterior.

---

## Endpoints del núcleo

| Ruta              | Descripción                          | Auth |
|-------------------|--------------------------------------|------|
| `GET /`           | Redirige al dashboard                | —    |
| `GET /dashboard`  | Panel principal con apps registradas | —    |
| `GET /health`     | Health check (JSON)                  | —    |
| `GET /api/docs`   | Swagger UI (solo en DEBUG=true)      | —    |

---

## App de ejemplo: Contacts

Disponible en `/apps/contacts/`

| Ruta                          | Acción                        |
|-------------------------------|-------------------------------|
| `GET  /apps/contacts/`        | Listado con búsqueda + filtros |
| `GET  /apps/contacts/new`     | Formulario de creación         |
| `POST /apps/contacts/new`     | Guardar nuevo contacto         |
| `GET  /apps/contacts/{id}`    | Detalle de contacto            |
| `GET  /apps/contacts/{id}/edit` | Formulario de edición        |
| `POST /apps/contacts/{id}/edit` | Guardar cambios              |
| `POST /apps/contacts/{id}/delete` | Eliminar               |

---

## Crear una nueva webapp

### Opción A: Script de scaffolding (recomendado)

```bash
python scripts/new_app.py inventario \
    --prefix /apps/inventario \
    --description "Gestión de inventario de equipos" \
    --icon "📦"
```

Esto genera toda la estructura base.  
Luego registra el módulo en `main.py`:

```python
# main.py — añade esta línea junto a los otros imports
from apps.inventario import app_module  # noqa: F401
```

Reinicia el servidor. La nueva app aparecerá en el dashboard.

### Opción B: Manual paso a paso

Sigue esta checklist para crear `apps/mi_app/` desde cero:

```
□ 1. Crear carpeta:  apps/mi_app/
□ 2. Crear modelo:   apps/mi_app/models.py        (clase SQLAlchemy, hereda Base)
□ 3. Crear schemas:  apps/mi_app/schemas.py        (clases Pydantic Create/Read)
□ 4. Crear repo:     apps/mi_app/repositories/item_repository.py
□ 5. Crear service:  apps/mi_app/services/item_service.py
□ 6. Crear router:   apps/mi_app/routers/items.py  (usa Depends(require_auth))
□ 7. Crear __init__: apps/mi_app/__init__.py       (registra con AppRegistry)
□ 8. Crear templates: templates/mi_app/*.html      (extienden base/layout.html)
□ 9. Registrar en main.py: from apps.mi_app import app_module
```

### Estructura mínima de `__init__.py`

```python
from fastapi import FastAPI
from core.registry import AppRegistry

mi_app = FastAPI(title="Mi App")

from apps.mi_app.routers import items  # noqa
mi_app.include_router(items.router)

AppRegistry.register(
    name="mi_app",
    router=mi_app,
    prefix="/apps/mi-app",
    description="Descripción corta",
    icon="📋",
)

app_module = mi_app
```

### Proteger rutas con autenticación

```python
from typing import Annotated
from fastapi import Depends
from core.auth import require_auth

# Protege una ruta individual
Auth = Annotated[str, Depends(require_auth)]

@router.get("/privado")
async def ruta_privada(username: Auth):
    return {"user": username}
```

### Añadir un campo al formulario

1. **Modelo** (`models.py`): añade columna SQLAlchemy
2. **Schema** (`schemas.py`): añade campo Pydantic
3. **Repositorio** (`repositories/`): el campo se mapea automáticamente si usas `model_dump()`
4. **Template** (`templates/mi_app/form.html`): añade macro del campo
5. **Router** (`routers/items.py`): añade `Form(...)` en el handler POST

---

## Autenticación

### Cómo funciona

- Se usa **HTTP Basic Auth** estándar del navegador
- Las contraseñas se verifican contra `.htpasswd` (formato Apache)
- El archivo se recarga automáticamente si cambia (sin reiniciar el servidor)
- Soporte para hashes: **bcrypt** (recomendado), SHA1, APR1-MD5, texto plano

### Rutas públicas

Configura rutas que no requieren auth en `.env` o en `core/config.py`:

```python
PUBLIC_PATHS: List[str] = [
    "/health",
    "/static",
    "/favicon.ico",
    # Añade aquí rutas públicas
]
```

### Compatibilidad con htpasswd de Apache

El archivo `.htpasswd` es compatible con el utilitario Apache:

```bash
# Crear usuario con Apache htpasswd (alternativa)
htpasswd -B .htpasswd nuevo_usuario
```

---

## Base de datos

### Creación de tablas

Las tablas se crean automáticamente al arrancar si no existen  
(`Base.metadata.create_all` en el lifespan de `main.py`).

Para migraciones en producción, usa **Alembic**:

```bash
pip install alembic
alembic init alembic
# Configura alembic.ini con tu DATABASE_URL
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

### Crear tabla manualmente (sin Alembic)

```bash
python -c "
import asyncio
from core.database import engine, Base
import apps.mi_app.models  # Importa los modelos

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(main())
"
```

---

## Tests

```bash
pip install pytest pytest-asyncio httpx aiosqlite

# Ejecutar todos los tests
pytest tests/ -v

# Tests con cobertura
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```

Los tests usan **SQLite en memoria** — no necesitan PostgreSQL.

---

## Despliegue en producción (sin Docker)

### Con systemd (Linux, sin sudo para --user)

```bash
# Crear servicio de usuario
mkdir -p ~/.config/systemd/user/

cat > ~/.config/systemd/user/corporate-platform.service << 'EOF'
[Unit]
Description=Corporate Platform
After=network.target

[Service]
Type=simple
WorkingDirectory=/ruta/a/corporate_platform
ExecStart=/ruta/a/corporate_platform/.venv/bin/python start.py
Restart=on-failure
RestartSec=5
EnvironmentFile=/ruta/a/corporate_platform/.env

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable corporate-platform
systemctl --user start corporate-platform
systemctl --user status corporate-platform

# Ver logs
journalctl --user -u corporate-platform -f
```

### Detrás de nginx (proxy inverso)

```nginx
server {
    listen 80;
    server_name intranet.empresa.com;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /ruta/a/corporate_platform/static/;
        expires 7d;
    }
}
```

### Con nohup (sin systemd)

```bash
nohup python start.py --workers 2 > logs/platform.log 2>&1 &
echo $! > platform.pid

# Detener
kill $(cat platform.pid)
```

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError` | Activar el venv: `source .venv/bin/activate` |
| Error de conexión a BD | Verificar `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` en `.env` |
| 401 en todas las rutas | Verificar que `.htpasswd` existe y tiene el formato correcto |
| Templates no encontradas | Ejecutar desde la raíz del proyecto (`corporate_platform/`) |
| Puerto en uso | Usar `--port 9000` o matar el proceso: `lsof -ti:8000 \| xargs kill` |
| `bcrypt` no instalado | `pip install bcrypt` |

---

## Decisiones de diseño

**¿Por qué FastAPI y no Flask?**  
FastAPI ofrece validación automática con Pydantic, tipado nativo, soporte async sin friction, y documentación OpenAPI automática. Para una plataforma que crecerá con múltiples apps, la productividad y fiabilidad justifican la curva de aprendizaje mínima.

**¿Por qué async?**  
En un entorno corporativo con múltiples usuarios concurrentes y consultas a BD, async evita bloqueos sin necesidad de múltiples workers.

**¿Por qué un AppRegistry?**  
Permite añadir/quitar apps con una sola línea en `main.py` sin modificar el núcleo. Cada app es completamente autónoma.

**¿Por qué htpasswd y no LDAP/OAuth?**  
El requisito es "sin sistemas externos". htpasswd es portable, sin dependencias, compatible con Apache (herramienta ya conocida en sysadmins), y permite rotación de credenciales sin reiniciar el servidor.
