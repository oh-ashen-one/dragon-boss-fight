#!/usr/bin/env python3
"""Collect source-matched native results without launching or changing the game.

Requires the complete packaged suite to match the delivered source identity.
Refuses missing/failed cases, source mismatches, renderer failures or an
unverified package. Physical input is recorded separately.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODES = {'core','controls','leg0','leg1','leg2','leg3','avoidance','healing','guard','death','victory','stance'}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def package(path):
    value=read(path)
    assert value['packagingSucceeded'] and value['uatSucceeded']
    assert len(value['bundleRepairs'])==1 and len(value['signedArchives'])==1
    repair=value['bundleRepairs'][0];signed=repair['signature']
    assert repair['originalArchiveUnchanged'] and repair['gameCodeIdentityUnchanged']
    assert signed['verified'] and signed['finalPathVerified'] and signed['extractedManifestMatchesSignedBundle']
    assert signed['extractionAudit']['staticDependencyAuditPassed']
    archive=value['signedArchives'][0]
    assert sha(archive['path'])==archive['sha256']
    identity=repair['sourceBuildIdentity'];build=read(identity['buildReceipt'])
    assert identity['embeddedStampVerified'] and build['success'] and build['sourceId']==identity['sourceId']
    return value,build


def run(path, expected):
    folder=Path(path).resolve();assert folder.is_relative_to(ROOT/'Evidence')
    candidates=list(folder.glob('unreal-*/evidence.json'));assert len(candidates)==1
    value=read(candidates[0]);launch=read(folder/'launch.json');gpu=read(folder/'gpu.json');preflight=read(folder/'bundle-preflight.json')
    assert value['sourceId']==expected and value['finished'] and value['finalWrite'] and value['passed']
    assert value['bothCustomuseCharactersActive'] and value['warningContainmentFailures']==0
    art=value['presentationAssets']
    assert all(art[key] for key in ('importedCathedral','generatedNightSky','generatedStoneFloor','importedBraziers','equippedWeaponVisible'))
    assert art['majorArchitecturePieces']==11 and '/BoatGreatsword_v004/SM_BoatGreatsword_v004' in art['equippedWeaponMesh']
    assert launch['runtimeKind']=='packaged-app' and gpu['exit_code']==0
    assert preflight['staticDependencyAuditPassed'] and preflight['signatureVerified'] and preflight['cookedPayloadPresent']
    return {'mode':value['mode'],'passed':True,'sourceId':expected,
            'durationGameSeconds':value['durationSeconds'],'terminalGameSeconds':value.get('terminalSeconds'),
            'reason':value['reason'],'evidenceSHA256':sha(candidates[0]),
            'evidence':str(candidates[0].relative_to(ROOT)),
            'executableSHA256':launch['executableSHA256'],
            'presentationAssets':art,
            'meanSimulationFrameSeconds':value['meanFrameSeconds'],
            'wallFrameP50Seconds':value.get('wallFrameP50Seconds'),
            'wallFrameP95Seconds':value.get('wallFrameP95Seconds'),
            'exclusivePerformanceValid':bool(gpu.get('perf_valid',False)),
            'video':{key:value['nativeVideo'].get(key) for key in
                     ['requestedFPS','savedFrames','failedFrames','skippedSlots','pngWriteSeconds','pixelCopySeconds']}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['package','suite','victory','physical','output']:
        p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();final,final_build=package(a.package)
    suite=read(a.suite);assert suite['finished'] and suite['sourceId']==final_build['sourceId']
    assert all(item['exitCode']==0 for item in suite['runs'])
    cases=[run(item['run'],final_build['sourceId']) for item in suite['runs']]
    cases.append(run(a.victory,final_build['sourceId']))
    assert len(cases)==len(MODES) and {item['mode'] for item in cases}==MODES
    victory=next(item for item in cases if item['mode']=='victory')
    assert 180<=victory['terminalGameSeconds']<=300
    physical=read(a.physical)
    assert physical['sourceId']==final_build['sourceId'] and physical['completed']
    required={'mouse_capture','movement','light_attack','heavy_attack','grip_toggle','jump','roll','guard','heal','lock_toggle','escape_release','reacquire','restart','post_restart_movement'}
    assert required<=physical['checks'].keys()
    assert all(physical['checks'][key] is True for key in required-{'roll'})
    assert physical['checks']['roll'] is True or (physical['checks']['roll'] is None and physical.get('rollInputLimitation'))
    report={'verified':True,'finalSourceId':final_build['sourceId'],
        'finalArchiveSHA256':final['signedArchives'][0]['sha256'],
        'architecture':'arm64 macOS','settings':{'resolution':[1280,720],'screenPercentage':100,'fpsCap':60},
        'packagedCases':cases,'allPackagedScenariosPassed':True,'packagedScenarioCount':len(MODES),
        'physicalInput':physical, 'allPhysicalKeysVerified':all(physical['checks'][key] is True for key in required),
        'limits':['Owner feel/difficulty judgement is separate from mechanical and rendered verification.',
                  'Capture is silent with real wall timestamps; shared GPU and capture work prevent exclusive performance claims.',
                  'Local ad-hoc signature; no notarization or other-platform acceptance.',
                  'Customuse character assets remain private pending raw public redistribution clearance.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'verified':True,'packagedCases':len(cases),'output':str(a.output)}))

if __name__=='__main__':main()
