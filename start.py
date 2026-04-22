#!/usr/bin/env python3
"""
start.py — Launch the Corporate Platform server.

Usage:
    python start.py                 # Uses settings from .env
    python start.py --port 9000
    python start.py --reload        # Dev mode with auto-reload
    python start.py --workers 4     # Production multi-process
"""
import argparse
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Corporate Platform launcher")
    parser.add_argument("--host",    default=None, help="Bind host")
    parser.add_argument("--port",    type=int, default=None, help="Bind port")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes")
    parser.add_argument("--reload",  action="store_true", help="Enable auto-reload (dev only)")
    parser.add_argument("--env",     default=".env", help="Path to .env file")
    return parser.parse_args()


def main():
    args = parse_args()

    # Load .env before importing settings
    if os.path.exists(args.env):
        from dotenv import load_dotenv
        load_dotenv(args.env)
        print(f"  Loaded config from: {args.env}")
    else:
        print(f"  Warning: {args.env} not found. Using environment variables.")

    from core.config import settings

    host    = args.host    or settings.HOST
    port    = args.port    or settings.PORT
    workers = args.workers or settings.WORKERS
    reload  = args.reload  or settings.DEBUG

    import uvicorn

    print(f"""
  ╔══════════════════════════════════════════╗
  ║        Corporate Platform  v{settings.APP_VERSION:<10} ║
  ╠══════════════════════════════════════════╣
  ║  URL       http://{host}:{port:<20} ║
  ║  Env       {settings.ENVIRONMENT:<30} ║
  ║  Workers   {workers:<30} ║
  ║  Reload    {str(reload):<30} ║
  ╚══════════════════════════════════════════╝
""")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=1 if reload else workers,
        reload=reload,
        reload_dirs=[".", "apps", "core", "templates"] if reload else None,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=False,   # Handled by our RequestLoggingMiddleware
    )


if __name__ == "__main__":
    main()
