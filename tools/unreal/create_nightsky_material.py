"""Author the supplied moon and original night-sky shader in the owned editor.

Source preparation only; root invokes run() through native Unreal Python/MCP.
Never launches an editor or replaces existing assets. Matching owned assets may
be reused read-only; mismatched/partial assets are preserved; repaired material uses fresh v004.
"""
import datetime
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Local/art-pass-20261019/references/moon-disc-v1.png'
DEST = '/Game/ArtPass/Sky'
MATERIAL = DEST + '/M_CathedralNight_v004'
TEXTURE = DEST + '/T_MoonDisc_v001'
OWNER = 'Veyr.original-cathedral-night.v004'
TEXTURE_OWNER = 'Veyr.original-cathedral-night.v001'

# Pixel shader work is bounded: five cloud-noise octaves, one moon texture
# sample, one star cell and at most one occasional meteor. No translucent dome,
# GPU particles, gameplay tick, runtime allocations or engine texture downloads.
SHADER = r'''
float3 D = normalize(-ViewRay);
float3 M = normalize(MoonDirection.xyz);
float elevation = saturate(D.z);
float3 sky = lerp(Horizon.rgb, Zenith.rgb, pow(elevation, 0.55));
float2 uv = float2(atan2(D.y,D.x)*0.1591549431+0.5, acos(clamp(D.z,-0.99999,0.99999))*0.3183098862);

// Clouds sample the continuous world direction, not longitude UV. Opposite
// sides of atan2's wrap are the same3D location, so there is no meridian seam.
float3 q=D*float3(4.0,4.0,6.0)+Seconds*CloudSpeed*float3(0.035,0.012,0.003);
float cloudNoise=0.0, amplitude=0.52;
[unroll] for(int octave=0;octave<5;++octave)
{
    float3 cell3=floor(q), blend3=frac(q);blend3=blend3*blend3*(3.0-2.0*blend3);
    float3 hashAxis=float3(127.1,311.7,74.7);
    float c000=frac(sin(dot(cell3,hashAxis))*43758.5453);
    float c100=frac(sin(dot(cell3+float3(1,0,0),hashAxis))*43758.5453);
    float c010=frac(sin(dot(cell3+float3(0,1,0),hashAxis))*43758.5453);
    float c110=frac(sin(dot(cell3+float3(1,1,0),hashAxis))*43758.5453);
    float c001=frac(sin(dot(cell3+float3(0,0,1),hashAxis))*43758.5453);
    float c101=frac(sin(dot(cell3+float3(1,0,1),hashAxis))*43758.5453);
    float c011=frac(sin(dot(cell3+float3(0,1,1),hashAxis))*43758.5453);
    float c111=frac(sin(dot(cell3+float3(1,1,1),hashAxis))*43758.5453);
    float plane0=lerp(lerp(c000,c100,blend3.x),lerp(c010,c110,blend3.x),blend3.y);
    float plane1=lerp(lerp(c001,c101,blend3.x),lerp(c011,c111,blend3.x),blend3.y);
    cloudNoise+=lerp(plane0,plane1,blend3.z)*amplitude;
    q=q*2.07+float3(19.2,7.6,11.3);amplitude*=0.48;
}
float clouds=smoothstep(0.38,0.70,cloudNoise)*CloudOpacity*smoothstep(-0.02,0.18,D.z);
float moonDot=clamp(dot(D,M),-1.0,1.0);
float rimLight=pow(saturate(moonDot),48.0);
float3 cloudLight=CloudColor.rgb*(0.38+1.4*rimLight);
sky=lerp(sky,cloudLight,clouds);

float2 starGrid=uv*float2(1200.0,600.0);
float2 cell=floor(starGrid), fstar=frac(starGrid);
cell.x=fmod(cell.x,1200.0);
float seed=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453);
float seed2=frac(sin(dot(cell,float2(269.5,183.3)))*43758.5453);
float2 center=0.2+0.6*float2(seed2,frac(seed*17.31));
float aa=clamp(max(length(ddx(D)),length(ddy(D)))*95.0,0.025,0.65);
float starPoint=1.0-smoothstep(0.06,0.06+aa,length(fstar-center));
float stars=starPoint*step(0.991,seed)*StarBrightness*(1.0-clouds)*smoothstep(0.06,0.24,D.z);
sky+=float3(0.68,0.79,1.0)*stars;

float3 right=normalize(cross(float3(0,0,1),M));
float3 up=normalize(cross(M,right));
float size=max(tan(MoonRadius),0.002);
float2 moonUV=0.5+float2(dot(D,right),-dot(D,up))/(max(moonDot,0.001)*size)*0.5;
float discRadius=length(moonUV*2.0-1.0);
float disc=(1.0-smoothstep(0.985,1.01,discRadius))*step(0.0,moonDot);
float4 moon=Texture2DSample(MoonTex,MoonTexSampler,saturate(moonUV));
float alpha=disc*moon.a;
float angle=acos(moonDot);
float halo=exp(-max(0.0,angle-MoonRadius)*24.0)*0.025*step(0.0,moonDot);
sky+=float3(0.60,0.73,1.0)*halo*(1.0-clouds*0.7);
sky=lerp(sky,moon.rgb*MoonBrightness,alpha*(1.0-clouds*0.86));

// One brief streak per period, with a gentle envelope and varying azimuth.
float cycle=floor(Seconds/max(12.0,MeteorPeriod));
float phase=frac(Seconds/max(12.0,MeteorPeriod));
float life=(phase-0.62)/0.022;
float envelope=smoothstep(0.0,0.12,life)*(1.0-smoothstep(0.72,1.0,life));
float2 start=float2(frac(0.47+cycle*0.381966),0.39+0.012*sin(cycle*2.4));
float2 travel=float2(0.058,0.018),head=start+travel*saturate(life);
float2 tail=head-travel*0.26,segment=head-tail;
float2 delta=uv-tail;delta.x-=round(delta.x);
float along=saturate(dot(delta,segment)/dot(segment,segment));
float distance=length(delta-segment*along);
float width=max(0.00018,fwidth(uv.y)*0.7);
float streak=(1.0-smoothstep(width,width*2.8,distance))*along*envelope*(1.0-clouds);
sky+=float3(0.48,0.65,1.0)*streak*0.85;
return max(sky,0.0);
'''


def run():
    if Path(unreal.Paths.project_dir()).resolve() != (ROOT/'Unreal/Veyr').resolve():
        raise RuntimeError('Incorrect owned project for night-sky creation')
    if not SOURCE.is_file():
        raise RuntimeError('Generated moon source is missing: ' + str(SOURCE))
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    recipe = hashlib.sha256((SHADER + source_hash + OWNER).encode()).hexdigest()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT/'Local/art-pass-20261019'/('night-sky-native-'+stamp+'.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {'success': False, 'nativeAppearanceAccepted': False, 'material': MATERIAL, 'texture': TEXTURE,
               'moonSource': str(SOURCE), 'moonSourceSHA256': source_hash, 'recipeSHA256': recipe,
               'moonDirectionWorld': [0.879385,0.410064,0.241922], 'shootingStarPeriodSeconds': 37.0}
    lib, assets = unreal.MaterialEditingLibrary, unreal.EditorAssetLibrary
    try:
        material = assets.load_asset(MATERIAL) if assets.does_asset_exist(MATERIAL) else None
        texture = assets.load_asset(TEXTURE) if assets.does_asset_exist(TEXTURE) else None
        if material is not None:
            if (not isinstance(material, unreal.Material) or assets.get_metadata_tag(material, 'VeyrOwner') != OWNER or
                    assets.get_metadata_tag(material, 'VeyrRecipe') != recipe):
                raise RuntimeError('Existing night material is not the exact owned recipe; no overwrite')
            if (not isinstance(texture, unreal.Texture2D) or assets.get_metadata_tag(texture, 'VeyrOwner') != TEXTURE_OWNER or
                    assets.get_metadata_tag(texture, 'VeyrSourceSHA256') != source_hash):
                raise RuntimeError('Matching material lacks its verified moon texture')
            receipt.update(success=True, reused=True)
            return material
        receipt['moonTextureReusedUnchanged'] = texture is not None
        if texture is not None:
            if (not isinstance(texture, unreal.Texture2D) or assets.get_metadata_tag(texture, 'VeyrOwner') != TEXTURE_OWNER or
                    assets.get_metadata_tag(texture, 'VeyrSourceSHA256') != source_hash):
                raise RuntimeError('Existing moon texture differs; no overwrite')
        else:
            task = unreal.AssetImportTask()
            for key, value in {'filename': str(SOURCE), 'destination_path': DEST, 'destination_name': 'T_MoonDisc_v001',
                               'automated': True, 'replace_existing': False, 'save': False}.items():
                task.set_editor_property(key, value)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            texture = assets.load_asset(TEXTURE)
            if not isinstance(texture, unreal.Texture2D):
                raise RuntimeError('Moon native texture import did not produce the canonical Texture2D')
            texture.set_editor_property('srgb', True)
            texture.set_editor_property('address_x', unreal.TextureAddress.TA_CLAMP)
            texture.set_editor_property('address_y', unreal.TextureAddress.TA_CLAMP)
            assets.set_metadata_tag(texture, 'VeyrOwner', TEXTURE_OWNER)
            assets.set_metadata_tag(texture, 'VeyrSourceSHA256', source_hash)
            if not assets.save_loaded_asset(texture, False):
                raise RuntimeError('Moon texture save failed')
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            'M_CathedralNight_v004', DEST, unreal.Material, unreal.MaterialFactoryNew())
        if not isinstance(material, unreal.Material):
            raise RuntimeError('Native material creation failed')
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
        material.set_editor_property('two_sided', True)
        material.set_editor_property('is_sky', True)
        nodes = []
        def node(kind, **props):
            expression = lib.create_material_expression(material, getattr(unreal, 'MaterialExpression'+kind), -900, len(nodes)*110)
            if expression is None:
                raise RuntimeError('Cannot create material expression: '+kind)
            for key, value in props.items():
                expression.set_editor_property(key, value)
            nodes.append(expression)
            return expression
        def scalar(name, default):
            return node('ScalarParameter', parameter_name=name, default_value=default)
        def vector(name, value):
            return node('VectorParameter', parameter_name=name, default_value=unreal.LinearColor(*value))
        inputs = {
            'ViewRay': node('CameraVectorWS'), 'Seconds': node('Time'),
            'MoonTex': node('TextureObjectParameter', parameter_name='MoonTexture', texture=texture),
            'MoonDirection': vector('MoonDirection', (.879385,.410064,.241922,0)),
            'Zenith': vector('ZenithColor', (.012,.022,.043,1)),
            'Horizon': vector('HorizonColor', (.052,.073,.105,1)),
            'CloudColor': vector('CloudColor', (.30,.35,.42,1)),
            'CloudSpeed': scalar('CloudSpeed', .015), 'CloudOpacity': scalar('CloudOpacity', .95),
            'StarBrightness': scalar('StarBrightness', .32), 'MoonRadius': scalar('MoonRadius', .09),
            'MoonBrightness': scalar('MoonBrightness', 1.7), 'MeteorPeriod': scalar('ShootingStarPeriod', 37.0)}
        custom_inputs = []
        for name in inputs:
            item = unreal.CustomInput()
            item.set_editor_property('input_name', name)
            custom_inputs.append(item)
        custom = node('Custom', code=SHADER, description='Original moonlit cathedral sky',
                      output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3, inputs=custom_inputs)
        for name, expression in inputs.items():
            if not lib.connect_material_expressions(expression, '', custom, name):
                raise RuntimeError('Native custom input connection failed: ' + name)
        if not lib.connect_material_property(custom, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR):
            raise RuntimeError('Native sky emissive connection failed')
        lib.layout_material_expressions(material)
        errors = [str(error) for error in lib.recompile_material(material)]
        receipt['compileErrors'] = errors
        if errors:
            raise RuntimeError('Native sky shader compilation failed')
        assets.set_metadata_tag(material, 'VeyrOwner', OWNER)
        assets.set_metadata_tag(material, 'VeyrRecipe', recipe)
        if not assets.save_loaded_asset(material, False):
            raise RuntimeError('Native sky material save failed')
        receipt.update(success=True, reused=False, expressionCount=len(nodes),
                       graphType='opaque two-sided unlit IsSky; supplied RGBA moon; original bounded procedural shader')
        return material
    except Exception as error:
        receipt['error'] = str(error)
        raise
    finally:
        output.write_text(json.dumps(receipt, indent=2)+'\n')
        unreal.log('VEYR_NIGHT_SKY_RECEIPT '+str(output))


if __name__ == '__main__':
    run()
