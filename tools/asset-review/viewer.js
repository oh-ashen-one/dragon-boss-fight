import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (id) => document.getElementById(id);
const viewport = $('viewport');
const canvas = $('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.35;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x273239);
const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
camera.position.set(4, 3, 6);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.screenSpacePanning = true;
controls.target.set(0, 1, 0);
controls.update();

scene.add(new THREE.HemisphereLight(0xd6e4e9, 0x40372f, 2.5));
const key = new THREE.DirectionalLight(0xffe2c4, 3.2);
key.position.set(4, 8, 6);
scene.add(key);
const rim = new THREE.DirectionalLight(0x9bbccc, 2.2);
rim.position.set(-6, 4, -5);
scene.add(rim);

const loader = new GLTFLoader();
const clock = new THREE.Clock();
const groupNames = { knight: 'Knight v015' };
const ordered = {
  knight: ['IdleTwoHand_ReadyBreath_v6', 'IdleOneHand_Breathing_v3', 'KnightRig'],
};
const approvedIds = new Set(['review/IdleTwoHand_ReadyBreath_v6.glb', 'review/IdleOneHand_Breathing_v3.glb']);

let catalog = [];
let activeGroup = 'knight';
let activeItem = null;
let model = null;
let grid = null;
let bones = null;
let mixer = null;
let action = null;
let duration = 0;
let playing = true;
let looping = true;
let wireframe = false;
let showBones = false;
let loadSerial = 0;

function humanName(item) {
  const names = {
    IdleOneHand_Breathing_v3: 'One-hand idle · approved',
    IdleTwoHand_ReadyBreath_v6: 'Two-hand idle · approved',
    KnightRig: 'Knight body · reference', DragonRig: 'Dragon body',
    BoatGreatsword_v4: 'Boat greatsword', CathedralFacade_v1: 'Cathedral facade',
    CathedralWall_v1: 'Cathedral wall', CathedralArch_v1: 'Cathedral arch',
    CathedralBrazier_v1: 'Cathedral brazier',
    Idle: 'Idle · one hand', IdleTwoHand: 'Two-hand idle · current',
    LightAttack: 'Light attack · one hand', LightAttackTwoHand: 'Light attack · two hands',
    HeavyAttack: 'Heavy attack · one hand', HeavyAttackTwoHand: 'Heavy attack · two hands',
    Guard: 'Guard · one hand', GuardTwoHand: 'Guard · two hands',
  };
  if (item.group === 'dragon' && item.name === 'Idle') return 'Idle';
  return names[item.name] || item.name.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/(\d)([A-Z])/g, '$1 $2');
}

function sortItems(a, b) {
  const order = ordered[activeGroup] || [];
  const ia = order.indexOf(a.name), ib = order.indexOf(b.name);
  if (ia !== -1 || ib !== -1) return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  return a.name.localeCompare(b.name);
}

function renderList() {
  const items = catalog.filter(item => item.group === activeGroup).sort(sortItems);
  const list = $('asset-list');
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'asset-empty';
    empty.textContent = 'No model or move matches this search.';
    list.append(empty);
  }
  for (const item of items) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'asset-item' + (activeItem?.id === item.id ? ' active' : '');
    button.setAttribute('role', 'option');
    button.setAttribute('aria-selected', activeItem?.id === item.id ? 'true' : 'false');
    const name = document.createElement('span');
    name.className = 'name'; name.textContent = humanName(item);
    const kind = document.createElement('span');
    kind.className = 'kind'; kind.textContent = approvedIds.has(item.id) ? 'approved' : item.id.startsWith('review/') ? 'review' : item.animationNames.length ? 'motion' : 'model';
    button.append(name, kind);
    button.addEventListener('click', () => selectItem(item));
    list.append(button);
  }
  $('asset-count').textContent = `${items.length} views`;
}

function setGroup(group) {
  activeGroup = group;
  renderList();
}

function loading(message, visible = true) {
  $('loading').classList.toggle('hidden', !visible);
  $('loading-text').textContent = message;
}

function disposeModel() {
  if (mixer) mixer.stopAllAction();
  if (bones) { scene.remove(bones); bones.geometry.dispose(); bones.material.dispose(); bones = null; }
  if (grid) { scene.remove(grid); grid.geometry.dispose(); grid.material.dispose(); grid = null; }
  if (model) {
    scene.remove(model);
    const geometries = new Set(), materials = new Set(), textures = new Set();
    model.traverse(node => {
      if (node.geometry) geometries.add(node.geometry);
      const mats = node.material ? (Array.isArray(node.material) ? node.material : [node.material]) : [];
      for (const mat of mats) materials.add(mat);
    });
    for (const material of materials) {
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
      material.dispose();
    }
    for (const texture of textures) texture.dispose();
    for (const geometry of geometries) geometry.dispose();
  }
  model = null; mixer = null; action = null; duration = 0;
}

function frameModel() {
  if (!model) return;
  const box = new THREE.Box3().setFromObject(model);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() * 0.5, 0.25);
  const fitMargin = activeItem?.name?.startsWith('IdleTwoHand') ? 0.9 : 0.68;
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov * 0.5)) * fitMargin;
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(distance * 0.4, distance * 0.18, distance));
  camera.near = Math.max(0.001, distance / 1000);
  camera.far = Math.max(1000, distance * 30);
  camera.updateProjectionMatrix();
  controls.minDistance = radius * 0.1;
  controls.maxDistance = radius * 25;
  controls.update();

  if (grid) { scene.remove(grid); grid.geometry.dispose(); grid.material.dispose(); }
  const gridSize = Math.max(2, Math.ceil(Math.max(size.x, size.z, size.y) * 2));
  grid = new THREE.GridHelper(gridSize, 16, 0x627277, 0x3e5157);
  grid.position.y = box.min.y - Math.max(0.005, size.y * 0.003);
  grid.material.transparent = true;
  grid.material.opacity = 0.4;
  scene.add(grid);
}

function frameBody() {
  if (!model) return;
  const body = model.getObjectByName('Hips');
  if (!body) return;
  const center = body.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(0, 0.12, 0));
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(0.50, 0.28, 1.9));
  controls.update();
}

function frameGrip() {
  if (!model) return;
  const right = model.getObjectByName('RightHand');
  const left = model.getObjectByName('LeftHand');
  if (!right || !left) return;
  const center = right.getWorldPosition(new THREE.Vector3()).add(left.getWorldPosition(new THREE.Vector3())).multiplyScalar(0.5);
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(0.20, 0.10, 0.52));
  controls.update();
}

const swordGrip = new THREE.Vector3(0.0616763, -0.00199617, 0.00555098);
const swordRotation = new THREE.Quaternion(0.78155554, 0.0047625, 0.01463231, -0.62364586);
const swordScale = 0.4096359622825952;

async function attachSword(knight, serial, item) {
  const hand = knight.getObjectByName('RightHand');
  if (!hand) throw new Error('Knight RightHand bone is missing');
  const twoHandReview = item.id === 'review/IdleTwoHand_ReadyBreath_v6.glb';
  const swordId = twoHandReview ? 'review/BoatGreatsword_Grip_v6.glb' : 'objects/BoatGreatsword_v4.glb';
  const sword = await loader.loadAsync(`/api/asset/${encodeURIComponent(swordId)}`);
  if (serial !== loadSerial) { disposeGltf(sword); return false; }
  sword.scene.position.copy(swordGrip);
  if (twoHandReview) sword.scene.position.add(new THREE.Vector3(0, 0.075 * swordScale, 0).applyQuaternion(swordRotation));
  sword.scene.quaternion.copy(swordRotation);
  sword.scene.scale.setScalar(swordScale);
  hand.add(sword.scene);
  return true;
}

function updatePlaybackControls() {
  const hasClip = !!action;
  $('play-button').disabled = !hasClip;
  $('timeline').disabled = !hasClip;
  $('speed').disabled = !hasClip;
  $('loop-button').disabled = !hasClip;
  $('play-button').textContent = hasClip && playing ? 'Ⅱ' : '▶';
  $('play-button').setAttribute('aria-label', hasClip && playing ? 'Pause animation' : 'Play animation');
  $('loop-button').textContent = looping ? 'Loop on' : 'Loop off';
  $('loop-button').setAttribute('aria-pressed', looping ? 'true' : 'false');
  $('clip-name').textContent = activeItem?.animationNames.join(', ') || 'Static model';
}

function timeText(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, '0')}.${String(Math.floor((seconds % 1) * 10))}`;
}

function updateTime() {
  const elapsed = action ? (duration ? action.time % duration : 0) : 0;
  $('time-label').textContent = `${timeText(elapsed)} / ${timeText(duration)}`;
  $('timeline').value = duration ? String(Math.round(elapsed / duration * 1000)) : '0';
}

function toggleWireframe(value) {
  wireframe = value;
  model?.traverse(node => {
    const mats = node.material ? (Array.isArray(node.material) ? node.material : [node.material]) : [];
    for (const mat of mats) if ('wireframe' in mat) mat.wireframe = wireframe;
  });
  $('wire-button').setAttribute('aria-pressed', String(wireframe));
}

function toggleBones(value) {
  showBones = value;
  if (bones) bones.visible = showBones;
  $('bones-button').setAttribute('aria-pressed', String(showBones));
}

function selectItem(item) {
  const serial = ++loadSerial;
  activeItem = item;
  setGroup(item.group);
  $('stage-group').textContent = approvedIds.has(item.id) ? 'Knight v015 · approved motion' : item.id.startsWith('review/') ? 'Knight v015 · review candidate' : groupNames[item.group];
  $('stage-title').textContent = humanName(item);
  window.history.replaceState(null, '', `#${encodeURIComponent(item.id)}`);
  loading(`Loading ${humanName(item)}…`);
  loader.load(`/api/asset/${encodeURIComponent(item.id)}`,
    async gltf => {
      if (serial !== loadSerial) { disposeGltf(gltf); return; }
      disposeModel();
      model = gltf.scene;
      scene.add(model);
      bones = new THREE.SkeletonHelper(model);
      bones.visible = showBones;
      scene.add(bones);
      try {
        if (item.group === 'knight') {
          loading('Attaching the boat greatsword to the Knight’s right hand…');
          if (!await attachSword(model, serial, item)) return;
        }
      } catch (error) {
        console.error(error);
        if (serial === loadSerial) loading('The Knight loaded, but the boat greatsword could not be attached.');
        return;
      }
      if (serial !== loadSerial) return;
      toggleWireframe(wireframe);
      if (gltf.animations.length) {
        mixer = new THREE.AnimationMixer(model);
        action = mixer.clipAction(gltf.animations[0]);
        duration = gltf.animations[0].duration;
        action.setLoop(looping ? THREE.LoopRepeat : THREE.LoopOnce, looping ? Infinity : 1);
        action.clampWhenFinished = true;
        action.play();
        mixer.setTime(0);
        playing = true;
      }
      model.updateMatrixWorld(true);
      frameModel();
      updatePlaybackControls();
      updateTime();
      renderList();
      loading('', false);
    },
    event => {
      if (serial !== loadSerial) return;
      if (event.lengthComputable) loading(`Loading ${humanName(item)}… ${Math.round(event.loaded / event.total * 100)}%`);
    },
    error => { if (serial === loadSerial) loading(`Could not load ${humanName(item)}. Check the Studio connection and try again.`); console.error(error); }
  );
}

function disposeGltf(gltf) {
  gltf.scene.traverse(node => {
    node.geometry?.dispose();
    if (node.material) (Array.isArray(node.material) ? node.material : [node.material]).forEach(material => material.dispose());
  });
}

function resize() {
  const width = viewport.clientWidth, height = viewport.clientHeight;
  if (!width || !height) return;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(viewport);

let hudAccum = 0;
function animate() {
  requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.1);
  if (mixer && playing) mixer.update(delta * Number($('speed').value));
  controls.update();
  renderer.render(scene, camera);
  hudAccum += delta;
  if (hudAccum > 0.05) { updateTime(); hudAccum = 0; }
}
animate();

$('frame-button').addEventListener('click', frameModel);
$('body-button').addEventListener('click', frameBody);
$('grip-button').addEventListener('click', frameGrip);
$('wire-button').addEventListener('click', () => toggleWireframe(!wireframe));
$('bones-button').addEventListener('click', () => toggleBones(!showBones));
$('play-button').addEventListener('click', () => { playing = !playing; updatePlaybackControls(); });
$('loop-button').addEventListener('click', () => {
  looping = !looping;
  if (action) action.setLoop(looping ? THREE.LoopRepeat : THREE.LoopOnce, looping ? Infinity : 1);
  updatePlaybackControls();
});
$('timeline').addEventListener('input', event => {
  if (!mixer || !action) return;
  playing = false;
  mixer.setTime(Number(event.target.value) / 1000 * duration);
  updatePlaybackControls(); updateTime();
});
document.addEventListener('keydown', event => {
  if (event.code !== 'Space' || !action || ['INPUT', 'SELECT', 'BUTTON'].includes(document.activeElement?.tagName)) return;
  event.preventDefault(); playing = !playing; updatePlaybackControls();
});

try {
  const response = await fetch('/api/catalog');
  if (!response.ok) throw new Error(`Catalog HTTP ${response.status}`);
  const data = await response.json();
  catalog = data.items;
  $('build-id').textContent = data.build;
  renderList();
  const requestedId = decodeURIComponent(location.hash.slice(1));
  const initial = catalog.find(item => item.id === requestedId) || catalog.find(item => item.id === 'review/IdleTwoHand_ReadyBreath_v6.glb') || catalog[0];
  if (initial) selectItem(initial);
  else loading('No active GLB assets found on the Studio.');
} catch (error) {
  console.error(error);
  loading('Could not reach the local asset server.');
}
