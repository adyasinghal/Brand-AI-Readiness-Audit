"""subprocess_isolation.py -- a real, OS-level timeout/cancellation guarantee for
work that might hang in a way a cooperative (software) timeout cannot bound.

Why this exists: a ThreadPoolExecutor future.result(timeout=N) (used elsewhere in
this project for the analysis DAG) can *detect* that a worker exceeded its budget,
but it cannot *stop* it -- Python offers no API to forcibly kill a thread, so an
abandoned thread keeps running in the background. That is an acceptable, honestly
documented limitation for the DAG's own analysis functions (they operate on
already-fetched in-memory data; the shared-memory threading model is an explicit
v4.0 architecture choice, not an oversight). It is NOT acceptable for the one step
in this pipeline that spawns real, potentially-unresponsive external processes:
headless browser rendering (Playwright launches an actual Chromium process, which
can hang or leave zombie processes behind a stuck IPC channel).

run_isolated() runs a target function in a genuine child process (multiprocessing,
not threading) and enforces a hard wall-clock deadline with join() + terminate()
+ kill() as a last resort. The parent process is *guaranteed* to regain control by
the deadline regardless of what the child (or anything the child spawned) does.
"""
from __future__ import annotations
import multiprocessing
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class IsolatedResult:
    ok: bool
    value: Any
    timed_out: bool
    error: Optional[str]


def _get_context():
    """Prefer "fork" (Linux/macOS default): it does not require the parent's
    __main__ module to be safely re-importable, which "spawn" does and which
    breaks under some test harnesses and REPL-style invocation. "fork" also
    starts faster. Falls back to the platform default (e.g. on Windows, which
    has no fork) when "fork" is unavailable."""
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        return multiprocessing.get_context()


def _double(x):
    """Test helper: must be module-level so it can be sent to a child process
    even under a "spawn" context (fork doesn't need this, but keeping it
    importable-by-reference works for both and is what real callers look like)."""
    return x * 2


def _hang_forever():
    """Test helper simulating a truly unresponsive child (e.g. a hung browser
    process) -- run_isolated must still return within its bounded deadline."""
    import time
    while True:
        time.sleep(1)


def _raises():
    raise ValueError("child blew up")


def _child_entry(target: Callable, args: tuple, kwargs: dict, queue) -> None:
    try:
        queue.put(("ok", target(*args, **kwargs)))
    except Exception as exc:  # noqa: BLE001 -- must never let the child crash silently
        queue.put(("error", repr(exc)))


def run_isolated(target: Callable, args: tuple = (), kwargs: dict | None = None,
                  timeout_s: float = 30.0, kill_grace_s: float = 2.0) -> IsolatedResult:
    """Runs target(*args, **kwargs) in a child process with a hard timeout.

    On timeout: terminate() (SIGTERM) is sent, then join(kill_grace_s); if the
    child is still alive, kill() (SIGKILL) is sent and joined again. The call
    always returns within approximately timeout_s + kill_grace_s, no matter how
    unresponsive the child (or a browser process it spawned) is.

    target and its args/return value must be picklable (plain strings, ints,
    lists, dicts -- exactly what the rendering call needs).
    """
    kwargs = kwargs or {}
    ctx = _get_context()
    queue: multiprocessing.Queue = ctx.Queue()
    proc = ctx.Process(target=_child_entry, args=(target, args, kwargs, queue), daemon=True)
    proc.start()
    proc.join(timeout_s)

    if proc.is_alive():
        proc.terminate()
        proc.join(kill_grace_s)
        if proc.is_alive():
            proc.kill()
            proc.join(kill_grace_s)
        return IsolatedResult(ok=False, value=None, timed_out=True,
                               error=f"exceeded {timeout_s}s and was killed")

    if not queue.empty():
        status, payload = queue.get()
        if status == "ok":
            return IsolatedResult(ok=True, value=payload, timed_out=False, error=None)
        return IsolatedResult(ok=False, value=None, timed_out=False, error=payload)

    # Process exited without putting anything on the queue (crash, segfault, killed
    # by the OS for another reason) -- never fabricate a result.
    return IsolatedResult(ok=False, value=None, timed_out=False,
                           error=f"child process exited with code {proc.exitcode} and no result")
