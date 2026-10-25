import bpy,json,os
from pathlib import Path
OWNER='codex-veyr-polish-20261025'
SRC=Path('/Users/midir/veyr-review-fable-20261021/Local/Blender')
OUT=Path(os.environ['VEYR_BLENDER_WORK']).parent
reports={}
for key,path in [('dragon',SRC/'dragon-v1-20261021/flight_r2/Dragon_FlyHover_Blender_v1r2.blend'),('knight',SRC/'feedback-v4-20261021/tripo_r2/run_Blender_v1.blend')]:
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False);s=bpy.context.scene;s['session_owner']=OWNER;s['mcp_port']=9891;s.frame_set(0)
 d={'source':str(path),'fps':s.render.fps,'range':[s.frame_start,s.frame_end],'objects':{},'scene':dict(s.items())}
 for o in s.objects:
  ad=o.animation_data
  d['objects'][o.name]={'type':o.type,'parent':o.parent.name if o.parent else None,'action':ad.action.name if ad and ad.action else None,'nla':[(t.name,[(st.name,st.action.name if st.action else None) for st in t.strips]) for t in ad.nla_tracks] if ad else [],'constraints':[(c.name,c.type,getattr(c,'subtarget','')) for c in o.constraints]}
  if o.type=='ARMATURE':
   d['objects'][o.name]['bones']={b.name:{'parent':b.parent.name if b.parent else None,'head':list(b.head),'tail':list(b.tail),'constraints':[(c.name,c.type,getattr(c,'subtarget',''),getattr(c,'chain_count',0),getattr(c,'pole_subtarget','')) for c in b.constraints]} for b in o.pose.bones}
 reports[key]=d
(OUT/'scene-audit.json').write_text(json.dumps(reports,indent=2,default=str))
print(json.dumps({k:{'fps':v['fps'],'range':v['range'],'armatures':[n for n,o in v['objects'].items() if o['type']=='ARMATURE'],'objects':list(v['objects'])} for k,v in reports.items()}))
