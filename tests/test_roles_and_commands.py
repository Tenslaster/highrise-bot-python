from pathlib import Path

import pytest

from highrise.tools.command_handler import Command, CommandHandler
from highrise.tools.roles import Roles


def test_roles_rejects_malformed_json(tmp_path: Path):
    path = tmp_path / "roles.json"
    path.write_text('{"mod": "not-a-list", "owner": [123, "u1"]}', encoding="utf-8")
    roles = Roles(path)
    assert roles.has_role("u1", "owner")
    assert not roles.has_role("u1", "mod")


def test_command_reload_removes_deleted_commands(tmp_path: Path):
    class DummyLogger:
        def warning(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass

    class DummyBot:
        logger = DummyLogger()
        roles = Roles(tmp_path / "roles.json")

    handler = CommandHandler(DummyBot())
    (tmp_path / "a.py").write_text(
        'from highrise.tools.command_handler import Command\n'
        'async def fn(ctx): pass\n'
        'command = Command("!a", fn)\n',
        encoding="utf-8",
    )
    handler.load_directory(str(tmp_path))
    assert "!a" in handler._commands

    (tmp_path / "a.py").unlink()
    handler.load_directory(str(tmp_path))
    assert "!a" not in handler._commands
