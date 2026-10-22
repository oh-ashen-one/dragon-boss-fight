import subprocess,sys,json,re
cmd=["python3","/Users/midir/veyr-review-fable-20261021/tools/art/blender/feedback_v4/run.py","--owner","fable-veyr-knight-walk-20261021","--port","9886"]+sys.argv[1:-2]+[sys.argv[-2],sys.argv[-1]]
p=subprocess.run(cmd,capture_output=True,text=True,cwd="/Users/midir/veyr-review-fable-20261021")
try:
    d=json.loads(p.stdout[p.stdout.index("{"):])
except Exception:
    print(p.stdout[-4000:],p.stderr[-4000:]);sys.exit(1)
res=d.get("result",d)
txt=res.get("result","") if isinstance(res,dict) else str(res)
if d.get("status")=="error" or "V4_RESULT" not in txt:
    print(json.dumps(d)[-6000:]);sys.exit(1)
other="\n".join(l for l in txt.splitlines() if not l.startswith("V4_RESULT"))
if other.strip():print(other[-3000:])
r=json.loads(txt.split("V4_RESULT ",1)[1].splitlines()[0])
print(json.dumps(r))
