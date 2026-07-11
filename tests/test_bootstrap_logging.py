from __future__ import annotations

import logging

from bootstrap.app import configure_workspace_file_logging


def test_configure_workspace_file_logging_is_idempotent(tmp_path) -> None:
    path1 = configure_workspace_file_logging(tmp_path)
    path2 = configure_workspace_file_logging(tmp_path)
    assert path1 == tmp_path / "logs" / "agent.log"
    assert path1 == path2

    logging.getLogger("infra.channels.ipc_server").info("ipc log smoke")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert "ipc log smoke" in path1.read_text(encoding="utf-8")
