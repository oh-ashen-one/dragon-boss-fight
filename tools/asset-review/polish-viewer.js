import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const $=id=>document.getElementById(id), viewport=$('viewport');
const renderer=new THREE.WebGLRenderer({canvas:$('stage'),antialias:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.35;
const scene=new THREE.Scene();scene.background=new THREE.Color(0x273239);
scene.add(new THREE.HemisphereLight(0xd6e4e9,0x40372f,2.5));
const key=new THREE.DirectionalLight(0xffe2c4,3.2);key.position.set(4,8,6);scene.add(key);
const rim=new THREE.DirectionalLight(0x9bbccc,2.2);rim.position.set(-6,4,-5);scene.add(rim);
const camera=new THREE.PerspectiveCamera(45,1,.01,1000), controls=new OrbitControls(camera,renderer.domElement);
controls.enableDamping=true;controls.dampingFactor=.07;controls.screenSpacePanning=true;
const loader=new GLTFLoader(), clock=new THREE.Clock();
let catalog=[], group='dragon', item=null, model=null, mixer=null, action=null, duration=0, playing=true, looping=true, wire=false, serial=0, grid=null;
let motionBounds=new THREE.Box3(), view='quarter';
function loading(text,show=true){$('loading-text').textContent=text;$('loading').classList.toggle('hidden',!show);}
function dispose(root){if(!root)return;const materials=new Set(),geometry=new Set(),textures=new Set();root.traverse(n=>{if(n.geometry)geometry.add(n.geometry);for(const m of n.material?(Array.isArray(n.material)?n.material:[n.material]):[])materials.add(m);});for(const m of materials){for(const v of Object.values(m))if(v?.isTexture)textures.add(v);m.dispose();}for(const t of textures)t.dispose();for(const g of geometry)g.dispose();}
function resize(){const w=viewport.clientWidth,h=viewport.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
new ResizeObserver(resize).observe(viewport);
function list(){
 for(const name of ['dragon','knight']){$(name+'-tab').classList.toggle('active',group===name);$(name+'-tab').setAttribute('aria-selected',String(group===name));}
 $('group-title').textContent=group==='dragon'?'Dragon':'Knight';
 const rows=catalog.filter(x=>x.group===group), host=$('asset-list');host.replaceChildren();$('asset-count').textContent=`${rows.length} candidates`;
 for(const row of rows){const b=document.createElement('button');b.type='button';b.className='asset-item'+(item?.id===row.id?' active':'');b.setAttribute('role','option');b.setAttribute('aria-selected',String(item?.id===row.id));const name=document.createElement('span');name.className='name';name.textContent=row.title.replace(/^(Dragon|Knight) · /,'');const state=document.createElement('span');state.className='kind';state.textContent='candidate';b.append(name,state);b.addEventListener('click',()=>select(row));host.append(b);}
}
function playback(){
 const enabled=!!action;for(const id of ['play-button','timeline','speed','loop-button'])$(id).disabled=!enabled;
 $('play-button').textContent=playing?'Ⅱ':'▶';$('play-button').setAttribute('aria-label',playing?'Pause animation':'Play animation');
 $('loop-button').textContent=looping?'Loop on':'Loop off';$('loop-button').setAttribute('aria-pressed',String(looping));
}
function updateTime(){const t=action?Math.min(action.time,duration):0;$('time-label').textContent=`${t.toFixed(2)} / ${duration.toFixed(2)} s`;$('timeline').value=duration?String(Math.round(t/duration*1000)):'0';}
function currentBounds(){model.updateMatrixWorld(true);model.traverse(n=>{if(n.isSkinnedMesh)n.skeleton.update();});return new THREE.Box3().setFromObject(model,true);}
function fit(bounds=motionBounds){
 if(bounds.isEmpty())return;const center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3());
 const radius=Math.max(size.length()*.5,.15), half=Math.min(THREE.MathUtils.degToRad(camera.fov*.5),Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov*.5))*camera.aspect));
 const distance=radius/Math.sin(half)*1.08;
 let direction=view==='front'?(item.group==='dragon'?new THREE.Vector3(1,.12,0):new THREE.Vector3(0,.12,1)):view==='side'?(item.group==='dragon'?new THREE.Vector3(0,.12,1):new THREE.Vector3(1,.12,0)):new THREE.Vector3(.8,.38,1);
 direction.normalize();controls.target.copy(center);camera.position.copy(center).addScaledVector(direction,distance);camera.near=Math.max(.001,distance/1000);camera.far=Math.max(1000,distance*30);camera.updateProjectionMatrix();controls.minDistance=radius*.15;controls.maxDistance=radius*25;controls.update();
}
function measureMotion(){
 const oldTime=action?.time||0,wasPlaying=playing;motionBounds.makeEmpty();
 if(action){action.reset().setLoop(THREE.LoopRepeat,Infinity).play();for(let i=0;i<=16;i++){mixer.setTime(duration*i/16*(1-1e-7));motionBounds.union(currentBounds());}action.reset().setLoop(looping?THREE.LoopRepeat:THREE.LoopOnce,looping?Infinity:1);action.clampWhenFinished=true;action.play();mixer.setTime(oldTime);}
 else motionBounds.copy(currentBounds());playing=wasPlaying;
 if(grid){scene.remove(grid);grid.geometry.dispose();grid.material.dispose();}
 const size=motionBounds.getSize(new THREE.Vector3());grid=new THREE.GridHelper(Math.max(2,Math.ceil(Math.max(size.x,size.z)*2)),16,0x627277,0x3e5157);grid.position.y=0;grid.material.transparent=true;grid.material.opacity=.4;scene.add(grid);
}
async function select(row){
 const token=++serial;item=row;group=row.group;list();loading(`Loading ${row.title}…`);$('stage-title').textContent=row.title;$('stage-group').textContent=`${group==='dragon'?'Dragon':'Knight'} · new review candidate`;$('grip-button').disabled=group!=='knight';
 history.replaceState(null,'',`#${encodeURIComponent(row.id)}`);
 try{
  const gltf=await loader.loadAsync(`/api/asset/${encodeURIComponent(row.id)}?v=${row.sha256}`);if(token!==serial){dispose(gltf.scene);return;}
  if(row.group==='knight'){
   const socket=gltf.scene.getObjectByName('ReviewWeaponSocket')||gltf.scene.getObjectByName('WeaponSocket');if(!socket)throw new Error('Authored weapon socket is missing');
   const prop=await loader.loadAsync(`/api/asset/${encodeURIComponent(row.weaponId)}?v=intact-v4`);if(token!==serial){dispose(gltf.scene);dispose(prop.scene);return;}
   // Never shrink or hide the shaft: identity attachment preserves the whole approved prop.
   prop.scene.position.set(0,0,0);prop.scene.quaternion.identity();prop.scene.scale.setScalar(1);socket.add(prop.scene);
  }
  if(model){scene.remove(model);mixer?.stopAllAction();dispose(model);}model=gltf.scene;scene.add(model);mixer=null;action=null;duration=0;looping=row.loop;playing=true;
  if(gltf.animations.length){mixer=new THREE.AnimationMixer(model);action=mixer.clipAction(gltf.animations[0]);duration=gltf.animations[0].duration;action.setLoop(looping?THREE.LoopRepeat:THREE.LoopOnce,looping?Infinity:1);action.clampWhenFinished=true;action.play();}
  model.traverse(n=>{for(const m of n.material?(Array.isArray(n.material)?n.material:[n.material]):[])if('wireframe'in m)m.wireframe=wire;});
  measureMotion();fit();mixer?.addEventListener('finished',()=>{playing=false;playback();});
  $('clip-name').textContent=row.file;$('asset-detail').textContent=`${duration.toFixed(2)} seconds · ${row.morphTargets} morph targets\n${row.group==='knight'?'Complete boat greatsword attached to the authored socket.':'Bone and morph animation play together.'}`;
  playback();updateTime();loading('',false);
 }catch(error){loading(`Could not load candidate: ${error.message}`);console.error(error);}
}
for(const name of ['dragon','knight'])$(name+'-tab').addEventListener('click',()=>{group=name;list();const first=catalog.find(x=>x.group===name);if(first&&item?.group!==name)select(first);});
$('frame-button').addEventListener('click',()=>fit());$('body-button').addEventListener('click',()=>{if(model)fit(currentBounds());});
for(const name of ['front','side','quarter'])$(name+'-button').addEventListener('click',()=>{view=name;fit();});
$('grip-button').addEventListener('click',()=>{if(!model||item.group!=='knight')return;const a=model.getObjectByName('LeftHand'),b=model.getObjectByName('RightHand');if(!a||!b)return;const bounds=new THREE.Box3().setFromPoints([a.getWorldPosition(new THREE.Vector3()),b.getWorldPosition(new THREE.Vector3())]).expandByScalar(.10);fit(bounds);});
$('wire-button').addEventListener('click',()=>{wire=!wire;$('wire-button').setAttribute('aria-pressed',String(wire));model?.traverse(n=>{for(const m of n.material?(Array.isArray(n.material)?n.material:[n.material]):[])if('wireframe'in m)m.wireframe=wire;});});
$('play-button').addEventListener('click',()=>{if(!action)return;if(!playing&&action.time>=duration-.0001)action.reset().play();playing=!playing;playback();});
$('loop-button').addEventListener('click',()=>{looping=!looping;if(action){action.setLoop(looping?THREE.LoopRepeat:THREE.LoopOnce,looping?Infinity:1);if(playing&&action.time>=duration-.0001)action.reset().play();}playback();});
$('timeline').addEventListener('input',event=>{if(!mixer||!action)return;playing=false;action.paused=false;action.enabled=true;mixer.setTime(Number(event.target.value)*duration/1000);playback();updateTime();});
document.addEventListener('keydown',event=>{if(event.code!=='Space'||!action||['INPUT','BUTTON','SELECT'].includes(document.activeElement?.tagName))return;event.preventDefault();$('play-button').click();});
let hud=0;function animate(){requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.1);if(mixer&&playing)mixer.update(dt*Number($('speed').value));controls.update();renderer.render(scene,camera);hud+=dt;if(hud>.05){updateTime();hud=0;}}resize();animate();
try{const response=await fetch('/api/catalog');if(!response.ok)throw new Error(`Catalog ${response.status}`);const data=await response.json();catalog=data.items;const requested=decodeURIComponent(location.hash.slice(1));await select(catalog.find(x=>x.id===requested||x.aliases?.includes(requested))||catalog.find(x=>x.group==='dragon')||catalog[0]);}catch(error){loading(`Reviewer unavailable: ${error.message}`);}
