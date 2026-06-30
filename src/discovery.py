"""
Module auto-discovery for the platform.

Convention: any package under `src/` (except `base/`, `db/`, `system/`)
that has a `router` attribute will be auto-registered.

To add a new business module:
1. Create `src/<module_name>/` package
2. Add `router = APIRouter(...)` in its `__init__.py` or `router.py`
3. Import the module's models in `src/<module_name>/__init__.py`
4. Done — no changes to main.py needed
"""
import importlib
import pkgutil
from pathlib import Path


# Core packages that are NOT business modules
CORE_PACKAGES = {"base", "db", "system", "main", "discovery", "rbac"}


def discover_routers():
    """Auto-discover routers from business module packages under src/."""
    routers: list[tuple[str, object]] = []

    src_path = Path(__file__).parent.parent / "src"
    for entry in src_path.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("_") or entry.name.startswith("."):
            continue
        if entry.name in CORE_PACKAGES:
            continue

        init_file = entry / "__init__.py"
        if not init_file.exists():
            continue

        try:
            mod = importlib.import_module(f"src.{entry.name}")
            if hasattr(mod, "router"):
                routers.append((entry.name, mod.router))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "failed to load business module %s: %s", entry.name, e
            )

    return routers
