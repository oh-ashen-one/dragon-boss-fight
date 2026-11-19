#!/usr/bin/env python3
"""Tests for engine_lock.py. No engine, no GPU: children are python or sleep. Run: python3 tools/unreal/test_engine_lock.py"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import warnings

warnings.simplefilter('ignore', ResourceWarning)  # test Popen pipes are closed by process exit
HERE = Path(__file__).resolve().parent
LOCK = HERE / 'engine_lock.py'
sys.path.insert(0, str(HERE))


def cli(env, label, *command, wait=60, **kw):
    return subprocess.Popen([sys.executable, str(LOCK), '--label', label, '--wait-seconds', str(wait), '--', *command],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)


def wait_for(predicate, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError('timed out waiting for condition')


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class EngineLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='veyr-lock-test-')
        self.dir = Path(self.tmp.name) / 'state'
        self.env = {**os.environ, 'VEYR_ENGINE_LOCK_DIR': str(self.dir)}
        self.env.pop('VEYR_ENGINE_LOCK_HELD', None)
        self.cleanup_pids = []

    def tearDown(self):
        for pid in self.cleanup_pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.tmp.cleanup()

    def holder(self):
        path = self.dir / 'holder.json'
        return json.loads(path.read_text()) if path.exists() else None

    def history(self):
        path = self.dir / 'history.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_mutual_exclusion_two_sleeping_children(self):
        marks = Path(self.tmp.name) / 'marks'
        script = ('import time,sys;f=open(sys.argv[1],"a");f.write("start "+sys.argv[2]+" %f\\n"%time.time());f.flush();'
                  'time.sleep(1.2);f.write("end "+sys.argv[2]+" %f\\n"%time.time());f.close()')
        a = cli(self.env, 'builder-A', sys.executable, '-c', script, str(marks), 'A')
        wait_for(lambda: self.holder() and self.holder()['label'] == 'builder-A')
        b = cli(self.env, 'builder-B', sys.executable, '-c', script, str(marks), 'B')
        status = subprocess.run([sys.executable, str(LOCK), '--status'], env=self.env, capture_output=True, text=True).stdout
        self.assertIn('builder-A', status)
        self.assertEqual(a.wait(timeout=30), 0)
        self.assertEqual(b.wait(timeout=30), 0)
        lines = [line.split() for line in marks.read_text().splitlines()]
        self.assertEqual([(k, n) for k, n, _ in lines], [('start', 'A'), ('end', 'A'), ('start', 'B'), ('end', 'B')])
        self.assertLessEqual(float(lines[1][2]), float(lines[2][2]))  # A ended before B started
        history = self.history()
        self.assertEqual([h['label'] for h in history], ['builder-A', 'builder-B'])
        self.assertGreater(history[1]['waitedSeconds'], 0.5)
        self.assertGreaterEqual(history[0]['heldSeconds'], 1.0)
        self.assertEqual(subprocess.run([sys.executable, str(LOCK), '--status'], env=self.env, capture_output=True, text=True).stdout.strip(), 'free')

    def test_waiters_are_served_oldest_first_so_builders_alternate(self):
        marks = Path(self.tmp.name) / 'order'
        script = 'import sys,time;open(sys.argv[1],"a").write(sys.argv[2]+"\\n");time.sleep(0.8)'
        first = cli(self.env, 'A1', sys.executable, '-c', script, str(marks), 'A1')
        wait_for(lambda: self.holder())
        second = cli(self.env, 'B1', sys.executable, '-c', script, str(marks), 'B1')
        time.sleep(0.4)
        third = cli(self.env, 'A2', sys.executable, '-c', script, str(marks), 'A2')  # A asks again before B ever ran
        for p in (first, second, third):
            self.assertEqual(p.wait(timeout=30), 0)
        self.assertEqual(marks.read_text().split(), ['A1', 'B1', 'A2'])

    def test_exit_code_passthrough_and_child_pid(self):
        p = cli(self.env, 'rc', sys.executable, '-c', 'import sys;sys.exit(7)')
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 7)
        self.assertRegex(err, r'child pid \d+')
        self.assertEqual(self.history()[-1]['exitCode'], 7)
        missing = cli(self.env, 'missing', '/nonexistent/binary')
        missing.communicate(timeout=30)
        self.assertEqual(missing.returncode, 127)

    def test_wait_timeout_exits_75_without_running(self):
        a = cli(self.env, 'long', 'sleep', '30')
        wait_for(lambda: self.holder())
        marker = Path(self.tmp.name) / 'ran'
        b = cli(self.env, 'impatient', 'touch', str(marker), wait=1)
        b.communicate(timeout=30)
        self.assertEqual(b.returncode, 75)
        self.assertFalse(marker.exists())
        a.send_signal(signal.SIGTERM)
        a.communicate(timeout=30)

    def test_signal_forwarding(self):
        flag = Path(self.tmp.name) / 'got-term'
        script = ('import signal,sys,time\n'
                  'def h(n,f):\n'
                  f'    open({str(flag)!r},"w").write(str(n)); sys.exit(42)\n'
                  'signal.signal(signal.SIGTERM,h)\n'
                  'print("ready",flush=True)\n'
                  'time.sleep(60)\n')
        for number, expected_code in ((signal.SIGTERM, 42),):
            p = cli(self.env, 'sig', sys.executable, '-c', script)
            wait_for(lambda: self.holder() and self.holder().get('child_pid'))
            time.sleep(0.5)  # let the child install its handler
            p.send_signal(number)
            p.communicate(timeout=30)
            self.assertEqual(p.returncode, expected_code)
            self.assertEqual(flag.read_text(), str(int(number)))
        # SIGINT reaches a child that does not handle it: the child dies by signal, the code is 128+2 and the lock is released
        p = cli(self.env, 'int', sys.executable, '-c', 'import time;time.sleep(60)')
        wait_for(lambda: self.holder() and self.holder().get('child_pid'))
        child = self.holder()['child_pid']
        p.send_signal(signal.SIGINT)
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 130)
        self.assertFalse(alive(child))
        self.assertIsNone(self.holder())

    def test_reentrant_nested_acquire_does_not_block(self):
        inner = ('import sys,time;sys.path.insert(0,%r)\nfrom engine_lock import engine_lock\n'
                 't=time.time()\nwith engine_lock("inner",quiet=True) as l:\n    print("reentrant",l.reentrant,"waited %%.2f"%%(time.time()-t))\n' % str(HERE))
        outer = ('import subprocess,sys\nr=subprocess.run([sys.executable,"-c",%r]);sys.exit(r.returncode)' % inner)
        p = cli(self.env, 'outer', sys.executable, '-c', outer)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        # the child printed through the inherited stdout of the CLI
        self.assertIn('reentrant True', out)
        self.assertEqual([h['label'] for h in self.history()], ['outer'])  # the nested acquire added no acquisition

    def test_env_token_without_live_holder_does_not_bypass(self):
        # A stale or forged token must not let a process in while somebody else really holds the lock.
        a = cli(self.env, 'real', 'sleep', '30')
        wait_for(lambda: self.holder())
        forged = {**self.env, 'VEYR_ENGINE_LOCK_HELD': 'deadbeef'}
        b = subprocess.run([sys.executable, str(LOCK), '--label', 'forger', '--wait-seconds', '1', '--', 'true'],
                           env=forged, capture_output=True, text=True, timeout=30)
        self.assertEqual(b.returncode, 75)
        a.send_signal(signal.SIGTERM)
        a.communicate(timeout=30)

    def test_module_context_manager_and_run(self):
        code = ('import sys,os;sys.path.insert(0,%r)\nfrom engine_lock import engine_lock\n'
                'with engine_lock("module",tree="/tmp/x") as l:\n'
                '    r=l.run([sys.executable,"-c","import os,sys;sys.exit(5 if os.environ.get(\'VEYR_ENGINE_LOCK_HELD\') else 9)"])\n'
                '    print("rc",r.returncode)\n'
                'print("after",os.environ.get("VEYR_ENGINE_LOCK_HELD"))\n' % str(HERE))
        r = subprocess.run([sys.executable, '-c', code], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertIn('rc 5', r.stdout)
        self.assertIn('after None', r.stdout)
        self.assertEqual(self.history()[-1]['tree'], '/tmp/x')

    def test_released_when_holder_sigkilled_no_child(self):
        code = ('import sys,time;sys.path.insert(0,%r)\nfrom engine_lock import engine_lock\n'
                'l=engine_lock("doomed",quiet=True).acquire();print("held",flush=True);time.sleep(60)\n' % str(HERE))
        holder = subprocess.Popen([sys.executable, '-c', code], env=self.env, stdout=subprocess.PIPE, text=True)
        self.assertEqual(holder.stdout.readline().strip(), 'held')
        holder.kill()  # SIGKILL
        holder.wait(timeout=10)
        t = time.time()
        p = cli(self.env, 'next', 'true', wait=10)
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertLess(time.time() - t, 5)
        self.assertTrue(any(h.get('event') == 'stale-holder-recovered' for h in self.history()))

    def test_sigkilled_holder_with_live_child_makes_next_wait_for_the_child(self):
        # CLI holder runs a child that survives the holder's SIGKILL (its own session). The flock is freed by the kernel,
        # but a second engine must still not start until that orphan is gone.
        p = cli(self.env, 'orphaning', sys.executable, '-c', 'import time;time.sleep(2.5)')
        wait_for(lambda: self.holder() and self.holder().get('child_pid'))
        child = self.holder()['child_pid']
        self.cleanup_pids.append(child)
        p.kill()  # SIGKILL the lock holder
        p.wait(timeout=10)
        self.assertTrue(alive(child))
        started = time.time()
        marker = Path(self.tmp.name) / 'second'
        q = cli(self.env, 'second', 'touch', str(marker), wait=30)
        q.communicate(timeout=30)
        self.assertEqual(q.returncode, 0)
        self.assertGreater(time.time() - started, 1.0, 'the second launch must wait for the orphan')
        self.assertFalse(alive(child))
        self.assertTrue(marker.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
