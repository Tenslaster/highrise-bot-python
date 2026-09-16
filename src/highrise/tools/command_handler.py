from dataclasses import dataclass, field
from typing import Callable, Coroutine, Any, TYPE_CHECKING
import importlib.util
from pathlib import Path

if TYPE_CHECKING:
    from ..base_bot import BaseBot

@dataclass
class Command:
    """Metadata + handler for a single command.

    Every handler receives a single `context: dict`. `bot` is always
    guaranteed to be present; everything else (e.g. `user`,
    `message`) is entirely up to whatever the caller passes in when
    dispatching. Handlers destructure only the keys they actually need.

    `required_roles`, if set, restricts dispatch to users holding that
    role. The caller must include either `user_id` or `user` (an
    object with an `.id` attribute) in context for the check to run,
    if neither is present, the command is treated as unauthorized and
    silently skipped.
    """
    name: str
    handler: Callable[[dict], Coroutine[Any, Any, None]]
    description: str = ""
    required_roles: list[str] = field(default_factory=list)

class CommandHandler:
    """Loads command files from a directory and dispatches messages
    into them by name, tolerating any per-command failure without
    affecting the bot's main loop."""

    def __init__(self, bot: "BaseBot") -> None:
        self.bot = bot
        self._commands: dict[str, Command] = {}

    def load_directory(self, directory: str = "commands") -> None:
        """Imports every `.py` file in the given directory and registers
        any `command: Command` object it defines at module level.
        
        - Can be used to reload the commands.

        Each module is registered in ``sys.modules`` under the key
        ``highrise_commands.<stem>`` so that stateful imports inside
        command files share a single module instance rather than being
        silently duplicated on every reload.
        """
        import sys

        path = Path(directory).expanduser()
        if not path.is_dir():
            self.bot.logger.warning(f"Command directory '{directory}' not found, skipping.")
            return

        # Reload semantics: commands removed from disk must not remain registered.
        self._commands.clear()

        for file in path.glob("*.py"):
            if file.stem.startswith("_"):
                continue

            module_key = f"highrise_commands.{file.stem}"
            spec = importlib.util.spec_from_file_location(module_key, file)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            # Register in sys.modules *before* exec so that relative imports
            # and module-level state inside the command file are shared across
            # reloads rather than silently re-created as separate instances.
            sys.modules[module_key] = module
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                self.bot.logger.error(f"Failed to load command file '{file.name}': {e}", exc_info=True)
                sys.modules.pop(module_key, None)
                continue

            command = getattr(module, "command", None)
            if not isinstance(command, Command):
                self.bot.logger.warning(f"'{file.name}' has no top-level `command: Command` object, skipping.")
                continue

            self._register(command)

        self.bot.logger.info(f"Loaded {len(self._commands)} command(s) from '{directory}'.")

    def _register(self, command: Command) -> None:
        if command.name in self._commands:
            self.bot.logger.warning(f"Command name '{command.name}' is already registered, overwriting.")
        self._commands[command.name] = command

    def _resolve_user_id(self, context: dict) -> str | None:
        """Pulls a user id out of context, accepting either a raw
        `user_id` key or a `user` object with an `.id` attribute."""
        if "user_id" in context:
            return context["user_id"]

        user = context.get("user")
        if user is not None and hasattr(user, "id"):
            return user.id

        return None

    def _is_authorized(self, command: Command, context: dict) -> bool:
        """Checks the required_roles gate for a command. Fails closed
        (unauthorized) if the required user identity can't be resolved."""
        if not command.required_roles:
            return True

        user_id = self._resolve_user_id(context)
        if user_id is None:
            return False

        return self.bot.roles.has_any_role(user_id, command.required_roles)

    async def dispatch(self, trigger: str, **context: Any) -> bool:
        """Runs the matching command's handler if one exists. Returns
        `True` if a command was found and invoked, `False` otherwise.
        `bot` is always injected into context, every other key is
        exactly whatever the caller passed in.

        If the command has a `required_role` and the calling user
        doesn't hold it, dispatch silently does nothing but still
        returns `True`, since a matching command was found.

        Any exception inside the handler is caught and logged, never
        propagates to the caller.
        """
        command = self._commands.get(trigger)
        if command is None:
            return False

        full_context = {"bot": self.bot, **context}

        if not self._is_authorized(command, full_context):
            return True

        try:
            await command.handler(full_context)
        except Exception as e:
            self.bot.logger.error(f"Error running command '{trigger}': {e}", exc_info=True)

        return True