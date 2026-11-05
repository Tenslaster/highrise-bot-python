"""Drop-in aliasing for the official ``highrise`` package name.

Bots written against the official SDK begin with::

    from highrise import BaseBot, Position

To run such a bot unchanged on ``highrise_fast``, install the alias **once**,
before the bot module is imported::

    import highrise_fast
    highrise_fast.install_alias()

    from highrise import BaseBot, Position   # now served by highrise_fast

The alias lives in :data:`sys.modules` only -- nothing is written to disk -- and
:func:`uninstall_alias` removes it again.

Safety
------
If the *real* official SDK is already imported in the current interpreter,
:func:`install_alias` refuses to hijack it and reports the name as skipped.
That matters because many environments have both packages installed; silently
shadowing the official SDK would be a nasty surprise. Pass ``force=True`` to
override, or uninstall the official package (``pip uninstall highrise-bot-sdk``)
when migrating for real.

This module deliberately does *not* ship a fake top-level ``highrise`` package
inside the distribution: a real directory would shadow the official SDK for
every project sharing the environment, with no opt-out.
"""

from __future__ import annotations

import contextlib
import sys

__all__ = [
    "ALIASED_MODULES",
    "alias_active",
    "install_alias",
    "uninstall_alias",
]

#: alias name -> module name relative to ``highrise_fast`` (``""`` = package root)
ALIASED_MODULES: dict[str, str] = {
    "highrise": "",
    "highrise.compat_requests": "compat_requests",
    "highrise.extras": "extras",
    "highrise.models": "models",
    "highrise.models_webapi": "models_webapi",
    "highrise.validation": "validation",
    "highrise.webapi": "",
    "highrise.__main__": "__main__",
}

_SKIPPED = "skipped"

#: Submodule attributes this module attached to the package, so
#: :func:`uninstall_alias` removes exactly those and nothing else. ``models`` and
#: friends are genuine import-time attributes of ``highrise_fast``; deleting
#: them blindly would break ``highrise_fast.models_webapi`` for the rest of the
#: process.
_ATTACHED: set[str] = set()


def _is_ours(module: object) -> bool:
    """Return ``True`` when ``module`` is ``highrise_fast`` or one of its children."""
    import highrise_fast

    return module is highrise_fast or getattr(module, "__name__", "").startswith(
        "highrise_fast"
    )


def alias_active() -> bool:
    """Return ``True`` when :func:`install_alias` is currently in effect."""
    import highrise_fast

    return sys.modules.get("highrise") is highrise_fast


def install_alias(force: bool = False) -> dict[str, str]:
    """Register the official ``highrise`` module names as aliases.

    Parameters
    ----------
    force
        Replace an already-imported, non-``highrise_fast`` ``highrise`` module.
        Without it, a real official SDK that is already imported is left alone
        and reported as ``"skipped"``.

    Returns
    -------
    dict[str, str]
        ``alias name -> highrise_fast module name`` it now resolves to, or
        ``"skipped"`` when an unrelated module already owned that name.
    """
    import importlib

    import highrise_fast

    installed: dict[str, str] = {}

    # The parent must be registered before the submodules so that a later
    # ``import highrise.models`` finds its parent already in sys.modules.
    order = ["highrise", *sorted(a for a in ALIASED_MODULES if a != "highrise")]

    for alias in order:
        relative = ALIASED_MODULES[alias]
        target = (
            highrise_fast
            if not relative
            else importlib.import_module(f"highrise_fast.{relative}")
        )

        existing = sys.modules.get(alias)
        if existing is not None and existing is not target and not force:
            installed[alias] = _SKIPPED
            continue

        sys.modules[alias] = target
        installed[alias] = target.__name__

    # Expose submodules as attributes on the parent so that ``highrise.models``
    # works after ``import highrise`` alone.
    if sys.modules.get("highrise") is highrise_fast:
        for alias, relative in ALIASED_MODULES.items():
            if not relative:
                continue
            module = sys.modules.get(alias)
            if module is None or not _is_ours(module):
                continue
            leaf = alias.rsplit(".", 1)[1]
            if getattr(highrise_fast, leaf, None) is module:
                continue
            setattr(highrise_fast, leaf, module)
            _ATTACHED.add(leaf)

    return installed


def uninstall_alias() -> list[str]:
    """Remove every alias previously installed by :func:`install_alias`."""
    import highrise_fast

    removed: list[str] = []

    for alias in ALIASED_MODULES:
        module = sys.modules.get(alias)
        if module is not None and _is_ours(module):
            del sys.modules[alias]
            removed.append(alias)

    for leaf in sorted(_ATTACHED):
        with contextlib.suppress(AttributeError):
            delattr(highrise_fast, leaf)
    _ATTACHED.clear()

    return removed
