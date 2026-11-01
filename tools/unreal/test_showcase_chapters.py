import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from showcase_chapters import LABELS,chapters


class ChapterTests(unittest.TestCase):
    def fixture(self,root):
        events=[];clock=1
        for name in LABELS:
            events.append({'event':'showcase_begin_'+name,'seconds':clock});clock+=1
            if name=='Flight':
                for event in ['dragon_Active','showcase_flight_fire_down','dragon_Recovery']:
                    events.append({'event':event,'seconds':clock,'showcase':{'currentSegment':'Flight'}});clock+=1
        manifest=root/'native-video/frames.jsonl';manifest.parent.mkdir()
        manifest.write_text(''.join(json.dumps({'type':'frame','worldIndex':0,'requestedGameSeconds':i,'wallSeconds':10+i*1.5})+'\n' for i in range(clock+1)))
        data={'mode':'showcase','finalWrite':True,'finished':True,'passed':True,'sourceId':'fixture',
              'showcase':{'requiredSegments':len(LABELS),'chapters':[{'passed':True} for _ in LABELS]},'events':events}
        evidence=root/'evidence.json';evidence.write_text(json.dumps(data))
        encode=root/'movie.encode.json';encode.write_text(json.dumps({'manifestSHA256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'timingVerified':True,'selectedWorldIndex':0,'sourceId':'fixture','videoSHA256':'fixture','encodedDurationSeconds':clock*1.5}))
        return evidence,encode

    def test_uses_capture_wall_time_instead_of_game_time(self):
        with tempfile.TemporaryDirectory() as d:
            e,v=self.fixture(Path(d));result=chapters(e,v)
            self.assertEqual(result['chapters'][0]['seconds'],1.5)
            self.assertEqual(len(result['chapters']),23)
            self.assertEqual(result['chapters'][-1]['seconds'],34.5)

    def test_missing_move_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            e,v=self.fixture(Path(d));data=json.loads(e.read_text());data['events']=data['events'][:-1];e.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'required move'):chapters(e,v)

    def test_changed_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            e,v=self.fixture(Path(d));m=e.parent/'native-video/frames.jsonl';m.write_text(m.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'verified world-0'):chapters(e,v)


if __name__=='__main__':unittest.main()
