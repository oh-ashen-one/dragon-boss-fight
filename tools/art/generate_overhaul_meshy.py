#!/usr/bin/env python3
"""Owner-authorized Meshy generation with direct, noninteractive downloads.
Secrets and expiring result URLs are never written to logs or receipts.
"""
import argparse,hashlib,json,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Local/Overhaul20261026/Meshy';OUT.mkdir(parents=True,exist_ok=True)
PROMPTS={
'GeneratedChandelier':'One monumental Gothic cathedral chandelier, an intact single hanging prop: two thick wrought-iron crown rings, twelve substantial candle cups with ivory wax candles, pointed Gothic tracery and connected forged scroll arms. Three sturdy suspension chains join a central top eye. Oxidized dark iron, aged bronze details, realistic soot and wax. Complete detailed underside, thick connected structure, four-meter diameter, no fabric lampshade. Isolated object only; no room, floor, pedestal, people, text, logos, flames or fog.',
'GeneratedVault':'A monumental ruined Gothic flying-buttress and pointed arch module for a dark fantasy cathedral. Two massive clustered stone piers joined by a very tall pointed arch with three parallel carved rib moldings and broken upper tracery. Open passage under the arch, real thick masonry, deep architectural sides and underside. Weathered grey limestone ashlar, soot-dark recesses and subtle damp moss. One coherent freestanding structural module with stable flat pier bases, no floor platform, no scene, no people, no text. Intended as an eighteen-meter-tall repeated vaulted bridge bay above a dragon arena.'}
def key():
 s=(Path.home()/'.agents-md/.secrets/meshy.env').read_text();m=re.search(r'^\s*(?:export\s+)?MESHY_API_KEY\s*=\s*(.+)\s*$',s,re.M)
 if not m:raise RuntimeError('Meshy credential unavailable')
 return m.group(1).strip().strip('\"\'')
def api(path,payload=None):
 data=json.dumps(payload).encode() if payload is not None else None
 r=urllib.request.Request('https://api.meshy.ai'+path,data=data,headers={'Authorization':'Bearer '+key(),'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=90) as f:return json.load(f)
def main():
 a=argparse.ArgumentParser();a.add_argument('action',choices=['create','status','refine','download']);a.add_argument('name',choices=PROMPTS);args=a.parse_args();folder=OUT/args.name;folder.mkdir(exist_ok=True);receipt=folder/'receipt.json';r=json.loads(receipt.read_text()) if receipt.exists() else {'name':args.name,'provider':'Meshy','prompt':PROMPTS[args.name],'tasks':[]}
 if args.action=='create':
  if r['tasks']:raise RuntimeError('Existing job retained; use status')
  r['balanceBefore']=api('/openapi/v1/balance')['balance']
  payload={'mode':'preview','prompt':r['prompt'],'ai_model':'meshy-7.1','should_remesh':True,'topology':'triangle','target_polycount':50000,'target_formats':['glb']}
  job=api('/openapi/v2/text-to-3d',payload)['result'];r['tasks'].append({'id':job,'stage':'preview','request':payload})
 elif args.action=='refine':
  if len(r['tasks'])!=1:raise RuntimeError('Refine already created or preview missing')
  preview=api('/openapi/v2/text-to-3d/'+r['tasks'][0]['id']);assert preview['status']=='SUCCEEDED'
  payload={'mode':'refine','preview_task_id':preview['id'],'enable_pbr':True,'texture_resolution':'2k','texture_prompt':r['prompt'],'target_formats':['glb']}
  job=api('/openapi/v2/text-to-3d',payload)['result'];r['tasks'].append({'id':job,'stage':'refine','request':payload})
 else:
  task=r['tasks'][-1];result=api('/openapi/v2/text-to-3d/'+task['id'])
  task.update({k:result[k] for k in ['status','progress','consumed_credits','created_at','finished_at'] if k in result})
  if result['status']=='SUCCEEDED':
   thumb=folder/(task['stage']+'.png')
   if not thumb.exists() and result.get('thumbnail_url'):urllib.request.urlretrieve(result['thumbnail_url'],thumb)
  if args.action=='download':
   assert result['status']=='SUCCEEDED' and task['stage']=='refine'
   dest=folder/(args.name+'_Source.glb');urllib.request.urlretrieve(result['model_urls']['glb'],dest)
   task['download']={'file':str(dest.relative_to(ROOT)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size}
   r['balanceAfter']=api('/openapi/v1/balance')['balance']
 receipt.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'name':args.name,'tasks':[{k:t[k] for k in ('id','stage','status','progress','consumed_credits','download') if k in t} for t in r['tasks']]}))
if __name__=='__main__':main()
