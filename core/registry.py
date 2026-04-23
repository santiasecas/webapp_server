"""
App Registry - central registry for pluggable webapp modules.

Each app registers itself with:
  - name              — unique slug (e.g. 'example_app')
  - router            — FastAPI sub-application
  - prefix            — URL prefix (e.g. '/apps/example')
  - description       — shown on dashboard
  - icon              — emoji
  - visible           — show on dashboard
  - category          — grouping for dashboard
  - permission_required — if True, user must have an explicit DB permission row
                          (admins are always exempt). Default: False (open to all
                          authenticated users — preserves backward compatibility).
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _AppRegistry:
    """Singleton registry for all platform apps."""

    def __init__(self):
        self.apps: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        router,
        prefix: str,
        description: str = "",
        icon: str = "📦",
        visible: bool = True,
        category: str = "General",
        permission_required: bool = False,
    ) -> None:
        """
        Register an app module.

        Args:
            name:                Unique app identifier (slug-style)
            router:              FastAPI router or sub-application
            prefix:              URL prefix (e.g. '/apps/example')
            description:         Human-readable description
            icon:                Emoji icon for dashboard
            visible:             Show on dashboard
            category:            Grouping category
            permission_required: If True, users need an explicit DB permission
                                 (admins always exempt). Default False keeps
                                 backward compatibility for existing apps.
        """
        if name in self.apps:
            logger.warning(f"App '{name}' is already registered. Overwriting.")

        self.apps[name] = {
            "name": name,
            "router": router,
            "prefix": prefix,
            "description": description,
            "icon": icon,
            "visible": visible,
            "category": category,
            "permission_required": permission_required,
        }
        perm_label = " [permission_required]" if permission_required else ""
        logger.debug(f"Registered app: '{name}' at '{prefix}'{perm_label}")

    def get_app_list(self) -> List[Dict[str, Any]]:
        """Return list of visible apps for dashboard rendering."""
        return [
            info for info in self.apps.values()
            if info.get("visible", True)
        ]

    def get_app(self, name: str) -> Optional[Dict[str, Any]]:
        return self.apps.get(name)

    def get_app_by_prefix(self, path: str) -> Optional[Dict[str, Any]]:
        """Find the app whose prefix is a prefix of the given path."""
        for info in self.apps.values():
            if path.startswith(info["prefix"]):
                return info
        return None


AppRegistry = _AppRegistry()
