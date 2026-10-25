from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'Local/CustomuseAssets/Polish20261025/knight';NEW=ROOT/'Local/FabRigTesting/Exports'
MIX='https://www.mixamo.com/#/?page=1&query=sword%20and%20shield&type=Motion%2CMotionPack'
FAB='https://www.fab.com/listings/5b737d10-b4cd-4294-8f6b-757b9088039d'
ROWS=[
 dict(id='walk',title='Walking',before='WalkOneHand_Blender_v2r2.glb',after='Mixamo_Walk_v1.glb',provider='Mixamo',clip='Sword and Shield Walk',source=MIX,beforeLabel='Current · approved one-hand walk',note='Source carries a sword and shield. The original left-arm shield posture is retained; the knight carries its existing boat sword. No shield added.'),
 dict(id='attack',title='Sword attack',before='LightAttack_BlackKnightReference_Blender_v2r3.glb',after='Mixamo_Attack_v1.glb',provider='Mixamo',clip='Sword and Shield Slash',source=MIX,beforeLabel='Current · Blender light attack',note='Different attack styles: a diagonal slash (1.5s) versus our overhead light attack (2.8s). This is a motion/style comparison, not a controlled speed ranking. Source timing is intact; damage windows and transitions are not part of this test.'),
 dict(id='guard',title='Blocking / guard',before='GuardReadyTwoHand_Blender_v4r4.glb',after='Mixamo_Block_v1.glb',provider='Mixamo',clip='Sword and Shield Block',source=MIX,beforeLabel='Current · idle to two-hand guard',note='Different guard styles: our two-hand sword guard versus a source shield block. This tests retargeting and body motion, not a drop-in guard replacement. No shield added.'),
 dict(id='run',title='Running',before='RunTwoHand_Blender_polish_v2.glb',after='Fab_Run_v1.glb',provider='Fab · VanillaLoop',clip='A_RunFwd_Loop',source=FAB,beforeLabel='Current · two-hand run (Tripo base + Blender grip)',note='Source is unarmed running; the boat sword follows its right palm. Our version has a deliberate two-hand carry. Neither baseline nor result is labeled entirely custom mocap.'),
 dict(id='roll',title='Forward roll',before='Roll_Blender_polish_v2.glb',after='Fab_Roll_v1.glb',provider='Fab · VanillaLoop',clip='A_Roll_IdleFwd',source=FAB,beforeLabel='Current · Blender-refined roll',note='The source roll retains its full-body tuck and root travel. The long boat sword is attached faithfully; any floor/body intersections need a weapon-specific adaptation before gameplay use.'),
]
