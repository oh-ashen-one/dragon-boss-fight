"""Capture-manifest safety checks; synthetic fixtures are not gameplay evidence."""
import json
from pathlib import Path
import struct
import tempfile
import unittest

from encode_video import read_capture


class CaptureManifestTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name).resolve()
        self.rows = [{"type": "world_start", "requestedFPS": 60}]
        for index, seconds in enumerate([0.0, 1 / 60, 2 / 60], 1):
            name = f"frame-{index:06d}.png"
            # read_capture validates the PNG signature and IHDR dimensions;
            # encoding is covered separately against real rendered captures.
            (self.root / name).write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 16, 16))
            self.rows.append({"type": "frame", "file": name, "sourceId": "synthetic-test",
                              "wallSeconds": seconds, "width": 16, "height": 16})
        self.rows.append({"type": "world_end", "wallSeconds": .05})

    def read(self):
        manifest = self.root / "frames.jsonl"
        manifest.write_text("\n".join(json.dumps(row) for row in self.rows) + "\n")
        return read_capture(manifest)

    def test_accepts_60hz_without_retiming(self):
        _, frames, end, observed, dimensions = self.read()
        self.assertEqual([row["wallSeconds"] for row in frames], [0, 1 / 60, 2 / 60])
        self.assertEqual((end, observed, dimensions), (.05, True, (16, 16)))

    def test_rejects_out_of_order_completion_records(self):
        self.rows[1], self.rows[2] = self.rows[2], self.rows[1]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            self.read()

    def test_rejects_mixed_builds(self):
        self.rows[2]["sourceId"] = "different-build"
        with self.assertRaisesRegex(ValueError, "same nonempty native source"):
            self.read()

    def test_rejects_missing_frame(self):
        (self.root / "frame-000002.png").unlink()
        with self.assertRaisesRegex(ValueError, "Missing frame"):
            self.read()

    def test_rejects_path_escape(self):
        self.rows[2]["file"] = "../frame-000002.png"
        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.read()


if __name__ == "__main__":
    unittest.main()
