#!/usr/bin/env python3
"""Tests for stage_prune.py. No engine: temp folders only. Run: python3 -B -m unittest discover -s tools/unreal -p 'test_stage_prune.py'"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from stage_prune import remove_owned_stage


class StagePruneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()   # stands in for /private/tmp
        self.project = self.root / 'checkout/Unreal/Veyr'
        self.project.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, name='veyr-stage-abc123', owner=True, project=None):
        path = self.root / name
        (path / 'Mac').mkdir(parents=True)
        (path / 'Mac/payload.bin').write_bytes(b'x')
        if owner:
            (path / 'veyr-stage-owner.json').write_text(json.dumps({'project': str(project or self.project), 'receiptDirectory': '/x'}))
        return path

    def test_removes_owned_stage(self):
        path = self.stage()
        self.assertTrue(remove_owned_stage(path, self.project, tmp_root=self.root))
        self.assertFalse(path.exists())

    def test_refuses_without_owner_file(self):
        path = self.stage(owner=False)
        self.assertFalse(remove_owned_stage(path, self.project, tmp_root=self.root))
        self.assertTrue((path / 'Mac/payload.bin').exists())

    def test_refuses_other_project_owner(self):
        path = self.stage(project=self.root / 'other/Unreal/Veyr')
        self.assertFalse(remove_owned_stage(path, self.project, tmp_root=self.root))
        self.assertTrue(path.exists())

    def test_refuses_wrong_prefix(self):
        path = self.stage(name='other-stage-abc')
        self.assertFalse(remove_owned_stage(path, self.project, tmp_root=self.root))
        self.assertTrue(path.exists())

    def test_refuses_path_outside_tmp_root(self):
        nested = self.root / 'sub'
        nested.mkdir()
        path = nested / 'veyr-stage-abc'
        (path).mkdir()
        (path / 'veyr-stage-owner.json').write_text(json.dumps({'project': str(self.project)}))
        self.assertFalse(remove_owned_stage(path, self.project, tmp_root=self.root))
        self.assertTrue(path.exists())

    def test_refuses_symlink_to_owned_stage(self):
        real = self.stage()
        link = self.root / 'veyr-stage-link'
        link.symlink_to(real)
        self.assertFalse(remove_owned_stage(link, self.project, tmp_root=self.root))
        self.assertTrue(real.exists())

    def test_refuses_missing_and_corrupt_marker(self):
        self.assertFalse(remove_owned_stage(self.root / 'veyr-stage-none', self.project, tmp_root=self.root))
        path = self.stage(owner=False)
        (path / 'veyr-stage-owner.json').write_text('not json')
        self.assertFalse(remove_owned_stage(path, self.project, tmp_root=self.root))
        self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
