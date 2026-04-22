"""
App Registry - central registry for pluggable webapp modules.

Each app registers itself with:
  - a name
  - a URL prefix
  - a FastAPI router (or sub-application)
  - optional metadata (description, icon, etc.)
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
    ) -> None:
        """
        Register an app module.

        Args:
            name:        Unique app identifier (slug-style, e.g. 'example_app')
            router:      FastAPI router or sub-application
            prefix:      URL prefix (e.g. '/apps/example')
            description: Human-readable description shown on dashboard
            icon:        Emoji or CSS class for dashboard icon
            visible:     Whether to show on the dashboard
            category:    Grouping category for dashboard display
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
        }
        logger.debug(f"Registered app: '{name}' at '{prefix}'")

    def get_app_list(self) -> List[Dict[str, Any]]:
        """Return list of visible apps for dashboard rendering."""
        return [
            info for info in self.apps.values()
            if info.get("visible", True)
        ]

    def get_app(self, name: str) -> Optional[Dict[str, Any]]:
        return self.apps.get(name)


AppRegistry = _AppRegistry()
