from agent.plugins import Plugin


class ShellRestore(Plugin):
    name = "shell_restore"
    version = "0.2.0"
    desc = "Legacy disabled plugin; rm is governed by ResourcePolicy instead of rewrite."
