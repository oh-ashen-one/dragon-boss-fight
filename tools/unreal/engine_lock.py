#!/usr/bin/env python3
"""Machine-wide mutex for every Veyr build, cook, commandlet and game process.

Owner rule: one game/engine/build process at a time on this machine for this project, windowless ones included.
This lock makes that real so two builders (each in its own worktree) can interleave launches safely.

CLI
  engine_lock.py --label <text> [--wait-seconds 7200] -- <command...>   wait, run in the foreground, pass the exit code
  engine_lock.py --status                                               print the holder, or "free"

Module
  from engine_lock import engine_lock
  with engine_lock('label', tree=ROOT) as lock:
      lock.run(command, cwd=ROOT, ...)        # Popen + wait; records the child so an orphan is noticed

State in ~/.cache/veyr-engine/ (override with VEYR_ENGINE_LOCK_DIR):
  lock            exclusive fcntl.flock; the kernel drops it when the holder dies, even on SIGKILL
  holder.json     pid, label, command, start time, tree, token, child pid
  history.jsonl   one line per acquisition: label, tree, waited seconds, held seconds, exit code
  queue/          one ticket file per waiter, so waiters are served oldest first and two builders alternate

Re-entrant: the holder exports VEYR_ENGINE_LOCK_HELD=<token> to its children. A nested acquire with that variable set,
a matching holder.json token, a live holder pid and a lock that is really held does not block and does not write state.

If a holder was killed but its engine child is still running, the next acquirer keeps the flock and waits for that
child to exit first (matched by pid and command line), so a SIGKILLed driver can never let a second engine start.

Exit code 75 (as gpu_slot uses) means the lock wait ran out and nothing was started.
"""
import argparse
import contextlib
import datetime
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time

ENV_TOKEN = 'VEYR_ENGINE_LOCK_HELD'
EXIT_TIMEOUT = 75
DEFAULT_WAIT = 7200
ANNOUNCE_EVERY = 60.0
POLL = 0.25


class EngineLockTimeout(Exception):
    """The wait ran out; nothing was started."""


def lock_dir():
    return Path(os.environ.get('VEYR_ENGINE_LOCK_DIR') or Path.home() / '.cache/veyr-engine')


def _now_iso(ts=None):
    return datetime.datetime.fromtimestamp(time.time() if ts is None else ts, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError, TypeError):
        return True
    # A zombie still answers kill(0); treat it as gone.
    state = _ps(pid, 'stat')
    return state is not None and not state.startswith('Z')


def _ps(pid, field):
    try:
        out = subprocess.run(['/bin/ps', '-o', field + '=', '-p', str(int(pid))], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None
    return out or None


def _git_tree(start=None):
    try:
        out = subprocess.run(['git', '-C', str(start or os.getcwd()), 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return str(start or os.getcwd())


def read_holder():
    try:
        data = json.loads((lock_dir() / 'holder.json').read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def describe_holder(holder, now=None):
    now = time.time() if now is None else now
    if not holder:
        return 'unknown holder'
    held = now - holder.get('started', now)
    return (f"pid {holder.get('pid')} label '{holder.get('label')}' tree {holder.get('tree')} "
            f"held {held / 60:.1f} min, command: {' '.join(holder.get('command') or [])[:200]}")


def _write_json_atomic(path, data):
    tmp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    tmp.write_text(json.dumps(data, indent=1) + '\n')
    os.replace(tmp, path)


def _lock_is_held_elsewhere(path):
    """True when some open file description holds the flock (also one in this same process)."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _reentrant_holder():
    token = os.environ.get(ENV_TOKEN)
    if not token:
        return None
    holder = read_holder()
    if (holder and holder.get('token') == token and _pid_alive(holder.get('pid'))
            and _lock_is_held_elsewhere(lock_dir() / 'lock')):
        return holder
    return None


class EngineLock:
    def __init__(self, label, tree=None, wait_seconds=DEFAULT_WAIT, command=None, quiet=False):
        self.label = str(label)
        self.tree = str(tree) if tree else _git_tree()
        self.wait_seconds = wait_seconds
        self.command = list(command) if command else list(sys.argv)
        self.quiet = quiet
        self.reentrant = False
        self.token = None
        self.fd = None
        self.ticket = None
        self.waited = 0.0
        self.exit_code = None
        self._acquired_at = None
        self._previous_env = None

    # ----- queue tickets: oldest live waiter goes first -----
    def _take_ticket(self):
        qdir = lock_dir() / 'queue'
        qdir.mkdir(parents=True, exist_ok=True)
        self.ticket = qdir / f'{time.time_ns():020d}-{os.getpid()}-{secrets.token_hex(3)}'
        self.ticket.write_text(json.dumps({'pid': os.getpid(), 'label': self.label, 'tree': self.tree}) + '\n')

    def _my_turn(self):
        qdir = lock_dir() / 'queue'
        for entry in sorted(qdir.iterdir()):
            if entry == self.ticket:
                return True
            try:
                pid = int(entry.name.split('-')[1])
            except (IndexError, ValueError):
                pid = None
            if pid is not None and _pid_alive(pid):
                return False
            with contextlib.suppress(OSError):
                entry.unlink()  # a waiter that died without cleaning up
        return True

    def _drop_ticket(self):
        if self.ticket is not None:
            with contextlib.suppress(OSError):
                self.ticket.unlink()
            self.ticket = None

    # ----- acquire / release -----
    def acquire(self):
        held = _reentrant_holder()
        if held is not None:
            self.reentrant = True
            self.token = held['token']
            return self
        directory = lock_dir()
        directory.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(directory / 'lock', os.O_RDWR | os.O_CREAT, 0o600)  # O_CLOEXEC by default: never inherited
        start = time.time()
        deadline = start + self.wait_seconds if self.wait_seconds is not None else None
        last_announce = 0.0
        self._take_ticket()
        try:
            while True:
                if self._my_turn():
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        pass
                now = time.time()
                if deadline is not None and now >= deadline:
                    raise EngineLockTimeout(f'engine lock still held after {self.wait_seconds:.0f}s: ' + describe_holder(read_holder()))
                if not self.quiet and now - last_announce >= ANNOUNCE_EVERY:
                    last_announce = now
                    print(f"engine_lock: waiting for '{self.label}' ({now - start:.0f}s so far); held by {describe_holder(read_holder())}",
                          file=sys.stderr, flush=True)
                time.sleep(POLL)
            self._wait_for_orphan_child()
        except BaseException:
            self._drop_ticket()
            self._close_fd()
            raise
        self._drop_ticket()
        self._acquired_at = time.time()
        self.waited = self._acquired_at - start
        self.token = secrets.token_hex(8)
        self._write_holder()
        self._previous_env = os.environ.get(ENV_TOKEN)
        os.environ[ENV_TOKEN] = self.token
        if not self.quiet and self.waited >= 1:
            print(f"engine_lock: acquired '{self.label}' after {self.waited:.0f}s", file=sys.stderr, flush=True)
        return self

    def _wait_for_orphan_child(self):
        """We hold the flock. A previous holder may have died with its engine child still running; wait for that child."""
        stale = read_holder()
        if not stale:
            return
        child = stale.get('child_pid')
        if stale.get('pid') and not _pid_alive(stale['pid']):
            self._history({'event': 'stale-holder-recovered', 'label': stale.get('label'), 'tree': stale.get('tree'),
                           'pid': stale.get('pid'), 'exitCode': None, 'note': 'holder died without releasing; flock was freed by the kernel'})
        if not child or not _pid_alive(child):
            return
        recorded = stale.get('child_command') or ''
        if stale.get('child_lstart') and _ps(child, 'lstart') != stale['child_lstart']:
            return  # pid was reused by something else
        announced = 0.0
        deadline = time.time() + (self.wait_seconds or DEFAULT_WAIT)
        while _pid_alive(child):
            if time.time() > deadline:
                raise EngineLockTimeout(f'orphan child pid {child} of dead holder {stale.get("pid")} is still running: {recorded[:200]}')
            if not self.quiet and time.time() - announced >= ANNOUNCE_EVERY:
                announced = time.time()
                print(f"engine_lock: previous holder pid {stale.get('pid')} is dead but its child pid {child} is still running; waiting for it to exit",
                      file=sys.stderr, flush=True)
            time.sleep(POLL)

    def _write_holder(self):
        _write_json_atomic(lock_dir() / 'holder.json', {
            'pid': os.getpid(), 'label': self.label, 'command': self.command, 'tree': self.tree, 'token': self.token,
            'started': self._acquired_at, 'startedAt': _now_iso(self._acquired_at), 'child_pid': None, 'child_command': None})

    def note_child(self, pid):
        """Record the engine child so a later acquirer can tell if it outlived a killed holder."""
        if self.reentrant:
            return
        holder = read_holder()
        if holder and holder.get('token') == self.token:
            holder['child_pid'] = pid
            holder['child_command'] = _ps(pid, 'command')
            holder['child_lstart'] = _ps(pid, 'lstart')  # stable across exec; the command line is not (it may be pre-exec here)
            _write_json_atomic(lock_dir() / 'holder.json', holder)

    def run(self, command, **popen_kwargs):
        """Popen + wait with SIGTERM/SIGINT forwarded to the child; returns subprocess.CompletedProcess."""
        child = subprocess.Popen(command, **popen_kwargs)
        self.note_child(child.pid)
        restore = _forward_signals(child.pid) if threading.current_thread() is threading.main_thread() else {}
        try:
            code = child.wait()
        finally:
            for number, handler in restore.items():
                signal.signal(number, handler)
        return subprocess.CompletedProcess(command, code)

    def release(self):
        if self.reentrant or self.fd is None:
            return
        held = time.time() - self._acquired_at
        if self._previous_env is None:
            os.environ.pop(ENV_TOKEN, None)
        else:
            os.environ[ENV_TOKEN] = self._previous_env
        holder = read_holder()
        if holder and holder.get('token') == self.token:
            with contextlib.suppress(OSError):
                (lock_dir() / 'holder.json').unlink()
        self._history({'label': self.label, 'tree': self.tree, 'pid': os.getpid(), 'waitedSeconds': round(self.waited, 1),
                       'heldSeconds': round(held, 1), 'exitCode': self.exit_code})
        self._close_fd()

    def _close_fd(self):
        if self.fd is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            with contextlib.suppress(OSError):
                os.close(self.fd)
            self.fd = None

    def _history(self, record):
        record = {'at': _now_iso(), **record}
        with contextlib.suppress(OSError):
            with open(lock_dir() / 'history.jsonl', 'a') as stream:
                stream.write(json.dumps(record) + '\n')

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, tb):
        if self.exit_code is None:
            if exc_type is None:
                self.exit_code = 0
            elif exc_type is SystemExit:
                self.exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            else:
                self.exit_code = 1
        self.release()
        return False


def engine_lock(label, tree=None, wait_seconds=DEFAULT_WAIT, command=None, quiet=False):
    """Context manager: hold the machine-wide Veyr engine lock for exactly the body."""
    return EngineLock(label, tree=tree, wait_seconds=wait_seconds, command=command, quiet=quiet)


def _forward_signals(pid):
    """Forward SIGTERM and SIGINT to the child's process group (it runs in its own session). Returns handlers to restore."""
    def forward(number, _frame):
        try:
            os.killpg(pid, number)
        except (ProcessLookupError, PermissionError):
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, number)
    saved = {}
    for number in (signal.SIGTERM, signal.SIGINT):
        saved[number] = signal.signal(number, forward)
    return saved


def _status():
    holder = read_holder()
    lock_path = lock_dir() / 'lock'
    if holder and _lock_is_held_elsewhere(lock_path):
        print('held by ' + describe_holder(holder))
        if holder.get('child_pid'):
            print(f"  child pid {holder['child_pid']}: {_ps(holder['child_pid'], 'command') or holder.get('child_command')}")
        queue = lock_dir() / 'queue'
        waiting = []
        if queue.is_dir():
            for entry in sorted(queue.iterdir()):
                with contextlib.suppress(OSError, ValueError):
                    info = json.loads(entry.read_text())
                    if _pid_alive(info.get('pid')):
                        waiting.append(f"{info.get('label')} (pid {info.get('pid')}, {info.get('tree')})")
        if waiting:
            print('  waiting: ' + '; '.join(waiting))
        return 0
    if holder and holder.get('child_pid') and _pid_alive(holder['child_pid']):
        print(f"free, but the dead holder pid {holder.get('pid')} left child pid {holder['child_pid']} running: {holder.get('child_command')}")
        return 0
    print('free')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--label', help='who is launching and why, e.g. "builder-A cook"')
    parser.add_argument('--wait-seconds', type=float, default=DEFAULT_WAIT, help='give up (exit 75) after this long; default 7200')
    parser.add_argument('--status', action='store_true', help='print the holder, or "free"')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='-- <command...>')
    args = parser.parse_args(argv)
    if args.status:
        return _status()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not args.label or not command:
        parser.error('usage: engine_lock.py --label <text> [--wait-seconds N] -- <command...>')
    lock = engine_lock(args.label, wait_seconds=args.wait_seconds, command=command)

    def early_signal(number, _frame):
        raise SystemExit(128 + number)
    old = {n: signal.signal(n, early_signal) for n in (signal.SIGTERM, signal.SIGINT)}
    try:
        try:
            lock.acquire()
        except EngineLockTimeout as error:
            print('engine_lock: ' + str(error), file=sys.stderr)
            return EXIT_TIMEOUT
        for number, handler in old.items():
            signal.signal(number, handler)
        try:
            child = subprocess.Popen(command, start_new_session=True)
        except OSError as error:
            print(f'engine_lock: cannot start {command[0]}: {error}', file=sys.stderr)
            lock.exit_code = 127
            return 127
        lock.note_child(child.pid)
        print(f"engine_lock: child pid {child.pid} ({args.label})", file=sys.stderr, flush=True)
        _forward_signals(child.pid)
        code = child.wait()
        if code < 0:
            code = 128 - code
        lock.exit_code = code
        return code
    finally:
        for number, handler in old.items():
            signal.signal(number, handler)
        lock.release()


if __name__ == '__main__':
    sys.exit(main())
