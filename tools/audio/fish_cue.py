#!/usr/bin/env python3
"""Generate one reviewed-at-a-time Fish cue; secrets only from runtime input.

No automatic retries: a pending marker requires investigation before resubmission.
"""
import argparse,datetime,hashlib,json,os,urllib.request,urllib.error
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--key-file',type=Path);p.add_argument('--text-file',required=True,type=Path);p.add_argument('--voice',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
key=os.environ.get('FISH_API_KEY','').strip()
if not key and a.key_file:
 try:key=a.key_file.read_text().strip()
 except OSError:raise SystemExit('Fish credential file unavailable; no request sent')
if not key:raise SystemExit('Fish credential missing; no request sent')
text=a.text_file.read_text().strip();receipt=a.output.with_suffix('.receipt.json');pending=a.output.with_suffix('.pending.json')
if a.output.exists() or pending.exists():raise SystemExit('Output/pending request exists; inspect it before another paid request')
body={'text':text,'reference_id':a.voice,'format':'wav','sample_rate':44100,'temperature':.7,'top_p':.7,'normalize':False,'latency':'normal','max_new_tokens':1024}
meta={'model':'drama-3','voice':a.voice,'text':text,'utf8Bytes':len(text.encode()),'estimatedUSDAtPublishedListPrice':len(text.encode())*50/1000000,'estimatedUSDAtLaunchPromotion':len(text.encode())*10/1000000,'submittedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'pending','billingNote':'Estimate from published byte pricing, not an invoice.'}
a.output.parent.mkdir(parents=True,exist_ok=True);pending.write_text(json.dumps(meta,indent=2)+'\n');pending.chmod(0o600)
req=urllib.request.Request('https://api.fish.audio/v1/tts',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','model':'drama-3'})
try:
 with urllib.request.urlopen(req,timeout=120) as r:
  data=r.read();kind=r.headers.get('Content-Type','')
 if not data.startswith(b'RIFF'):raise ValueError('Expected WAV audio response')
 a.output.write_bytes(data);meta.update(status='completed',bytes=len(data),sha256=hashlib.sha256(data).hexdigest());receipt.write_text(json.dumps(meta,indent=2)+'\n');pending.unlink();print(json.dumps({'status':'completed','output':str(a.output),'estimatedUSD':meta['estimatedUSDAtLaunchPromotion']}))
except urllib.error.HTTPError as e:
 meta.update(status='http_error',httpStatus=e.code);receipt.write_text(json.dumps(meta,indent=2)+'\n');print('Fish API error status',e.code);raise SystemExit(1)
except Exception as e:
 print('Fish outcome uncertain; retain pending marker:',type(e).__name__);raise SystemExit(1)
