#!/usr/bin/env python3
"""Import only the two fixed fortress module plans through the owned native MCP."""
import argparse,hashlib,json,re,sys
from pathlib import Path
from native_mcp import NativeMCP
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Local/FortressModulesEditor20261103'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--asset',action='append',choices=['FortressMuralWall','FortressWatchtower','FortressCurtainWall','FortressPaintedWall','FortressBrazier','PolyHavenCoastalCliff']);parser.add_argument('--protected-baseline',type=Path,default=ROOT/'Local/FortressEditor20261103/protected-before.json');args=parser.parse_args()
    OUT.mkdir(exist_ok=True);c=NativeMCP(timeout=900);c.initialize()
    def meta(name,args):
        r=c.request('tools/call',{'name':name,'arguments':args})
        if r.get('error') or r.get('result',{}).get('isError'):raise RuntimeError('Native call failed: '+name)
        return r['result']['content'][0]['text']
    names=re.findall(r'^- ([^:\n]+):',meta('list_toolsets',{}).replace('\\n','\n'),re.M)
    target=[n for n in names if n.endswith('.veyr_integration_toolset.VeyrIntegrationTools') and 'veyr-knight-20261028' in n]
    assert len(target)==1,'Expected exactly the owned project toolset';toolset=target[0]
    schema=json.loads(meta('describe_toolset',{'toolset_name':toolset}));(OUT/'veyr-schema.json').write_text(json.dumps(schema,indent=2)+'\n')
    def call(name,args):
        raw=meta('call_tool',{'toolset_name':toolset,'tool_name':name,'arguments':args});result=json.loads(raw)['returnValue']
        if isinstance(result,str):result=json.loads(result)
        return result
    project=call('inspect_project',{});assert Path(project['project_directory']).resolve()==ROOT/'Unreal/Veyr'
    (OUT/'project-check.json').write_text(json.dumps(project,indent=2)+'\n')
    assert args.protected_baseline.resolve().is_relative_to(ROOT/'Local')
    protected=json.loads(args.protected_baseline.read_text())
    assert set(protected)==set(json.loads((ROOT/'Local/FortressEditor20261103/protected-before.json').read_text()))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in protected.items()),'Protected assets changed before import'
    for name in args.asset or ['FortressMuralWall','FortressWatchtower']:
        receipt=OUT/(name+'-import.json')
        if receipt.exists():
            previous=json.loads(receipt.read_text())
            if previous.get('success'):print(name,'already imported; retained');continue
            raise RuntimeError('Prior import failed; inspect before retry: '+name)
        r=call('import_polish_environment',{'asset_name':name});receipt.write_text(json.dumps(r,indent=2)+'\n')
        assert r.get('success'),name+' import failed'
        print(name,'imported and native LODs verified',flush=True)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in protected.items()),'Protected asset changed during environment import'
    (OUT/'protected-after.json').write_text(json.dumps(protected,indent=2)+'\n')
if __name__=='__main__':main()
