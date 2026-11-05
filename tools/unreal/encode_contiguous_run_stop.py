#!/usr/bin/env python3
"""Encode matched unannotated Blender run/stop studies with one encoder."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('review_directory',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args();review=a.review_directory.resolve(strict=True);out=a.output.resolve(strict=True)
    assert not a.receipt.exists()
    work=review/'encode';assert not work.exists();work.mkdir()
    records=[];command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n']
    baseline=None
    for side in ['before','after']:
        meta=json.loads((review/(side+'.json')).read_text())
        assert meta['reviewFPS']==30 and meta['groundHeightSourceUnits']==0
        if baseline is None:baseline=meta
        assert meta['viewOrthoScales']==baseline['viewOrthoScales'] and meta['frames']==baseline['frames']
        folder=work/side;folder.mkdir()
        files=[review/'Evidence'/side/f'{view}_{frame:04d}.png' for view in ['front','side','threequarter'] for frame in meta['frames']]
        assert all(path.is_file() for path in files)
        for i,path in enumerate(files):os.link(path,folder/f'frame-{i:06d}.png')
        movie=out/('contiguous-run-stop-'+side+'.mp4');assert not movie.exists()
        records.append({'variant':side,'movie':movie.name,'frames':len(files),'fps':30,'durationSeconds':len(files)/30,'sourcePoseReconstructionMaxError':meta['sourcePoseReconstructionMaxError'],'matchedFloorAndCamera':True,'editorialOverlays':False})
        command+=['-framerate','30','-i',str(folder/'frame-%06d.png')]
    for i,record in enumerate(records):
        command+=['-map',f'{i}:v:0','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-map_metadata','-1','-movflags','+faststart',str(out/record['movie'])]
    subprocess.run(command,check=True)
    for record in records:
        movie=out/record['movie']
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(movie)],text=True))
        stream=probe['streams'][0]
        assert int(stream['nb_frames'])==record['frames'] and stream['width']==stream['height']==960
        assert abs(float(probe['format']['duration'])-record['durationSeconds'])<.002
        record['sha256']=hashlib.sha256(movie.read_bytes()).hexdigest()
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps({'scope':'Matched sourced Blender studies with repeated lead-in and deceleration, not native gameplay or acceptance','movies':records,'sourceLicense':'CC BY3.0, Open Motion Project by ACCAD/The Ohio State University; adapted for Veyr'},indent=2)+'\n')
    shutil.rmtree(work)
    print('Verified two matched source movies; no editorial overlays')


if __name__=='__main__':main()
