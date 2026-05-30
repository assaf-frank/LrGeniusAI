"""Tests for server_lifecycle restart/shutdown — issue #197 (Windows /restart).

Restart is handled identically on every platform: spawn a detached copy of this
process, then terminate. Termination must release the port even when the launcher
ignores SIGINT (e.g. `uv run`), so a hard-exit watchdog is always armed.
"""

import sys

import server_lifecycle


def test_request_restart_spawns_then_shuts_down(mocker):
    spawn = mocker.patch.object(server_lifecycle, "_spawn_replacement")
    shutdown = mocker.patch.object(server_lifecycle, "request_shutdown")

    server_lifecycle.request_restart()

    spawn.assert_called_once()
    shutdown.assert_called_once()


def test_request_restart_shuts_down_even_if_spawn_fails(mocker):
    """A failed respawn must not leave the old process running forever."""
    mocker.patch.object(
        server_lifecycle, "_spawn_replacement", side_effect=OSError("boom")
    )
    shutdown = mocker.patch.object(server_lifecycle, "request_shutdown")

    server_lifecycle.request_restart()

    shutdown.assert_called_once()


def test_spawn_replacement_reuses_interpreter_and_argv(mocker):
    popen = mocker.patch.object(server_lifecycle.subprocess, "Popen")

    server_lifecycle._spawn_replacement()

    popen.assert_called_once()
    # Relaunch reuses this interpreter and the original argv (which carries --db-path).
    assert popen.call_args.args[0] == [sys.executable] + sys.argv


def test_terminate_process_arms_watchdog_and_signals(mocker):
    """Graceful SIGINT is attempted, and a hard-exit watchdog is armed as a
    fallback for launchers that ignore SIGINT. pid/OK files are cleaned up."""
    remove_pid = mocker.patch.object(server_lifecycle, "remove_pid_file")
    remove_ok = mocker.patch.object(server_lifecycle, "remove_ok_file")
    thread = mocker.patch.object(server_lifecycle.threading, "Thread")
    kill = mocker.patch.object(server_lifecycle.os, "kill")

    server_lifecycle._terminate_process()

    remove_pid.assert_called_once()
    remove_ok.assert_called_once()
    thread.assert_called_once()  # watchdog armed
    assert thread.call_args.kwargs.get("daemon") is True
    kill.assert_called_once()  # graceful SIGINT attempted
