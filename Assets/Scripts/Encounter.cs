using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

public sealed class Encounter:MonoBehaviour
{
    public static Encounter Instance;
    public PlayerCombat Player;public DragonBoss Boss;
    float hurtFlash, started, nextCapture; int frame; GUIStyle label,title,small;
    readonly List<float> frameMs=new List<float>();
    string captureDir;
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void StartGame(){if(!FindFirstObjectByType<Encounter>())new GameObject("Veyr Encounter").AddComponent<Encounter>();}
    void Awake(){
        Instance=this;Application.targetFrameRate=60;QualitySettings.vSyncCount=0;
        QualitySettings.antiAliasing=4;QualitySettings.shadowDistance=95;
        ArenaBuilder.Build();
        Player=new GameObject("Knight").AddComponent<PlayerCombat>();Player.transform.position=new Vector3(0,.05f,-16);Player.Initialize();
        Boss=new GameObject("Veyr — Cinder Warden").AddComponent<DragonBoss>();Boss.transform.position=new Vector3(0,0,5);Boss.Initialize(Player);Player.Boss=Boss;
        var cameraObj=new GameObject("Combat Camera");var cam=cameraObj.AddComponent<Camera>();cam.tag="MainCamera";cam.fieldOfView=60;cam.nearClipPlane=.15f;cam.farClipPlane=450;cam.allowHDR=true;
        cameraObj.AddComponent<AudioListener>();cameraObj.transform.position=Player.transform.position+new Vector3(0,4,-8);
        CombatAudio.Initialize();
        var follow=cameraObj.AddComponent<CombatCamera>();follow.Player=Player;follow.Boss=Boss;Player.View=cam;
        Cursor.lockState=CursorLockMode.None;Cursor.visible=true;started=Time.time;
        var args=Environment.GetCommandLineArgs();for(int i=0;i<args.Length-1;i++)if(args[i]=="--capture-dir"){captureDir=Path.GetFullPath(args[i+1]);Directory.CreateDirectory(captureDir);nextCapture=3;}
        if(Array.IndexOf(args,"--replay")>=0){Application.runInBackground=true;new GameObject("Combat Replay Driver").AddComponent<CombatReplay>();}
        for(int i=0;i<args.Length-1;i++)if(args[i]=="--record-dir")new GameObject("Native Gameplay Recorder").AddComponent<NativeRecorder>().Initialize(args[i+1]);
    }
    void Update(){
        hurtFlash=Mathf.Max(0,hurtFlash-Time.deltaTime*1.7f);frame++;
        if(Time.time-started>3&&frameMs.Count<60000)frameMs.Add(Time.unscaledDeltaTime*1000);
        if(Input.GetKeyDown(KeyCode.R))RestartEncounter();
        if(Input.GetKeyDown(KeyCode.F12))Capture();
        if(captureDir!=null&&Time.time-started>=nextCapture){Capture();nextCapture+=5;}
    }
    public void FlashDamage(){hurtFlash=.45f;}
    public void RestartEncounter(){if(Player.IsDead||Boss.IsDead)SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);}
    void Capture(){
        if(captureDir==null)captureDir=Path.Combine(Application.persistentDataPath,"captures");Directory.CreateDirectory(captureDir);
        ScreenCapture.CaptureScreenshot(Path.Combine(captureDir,"gameplay-"+frame.ToString("D06")+".png"));
        File.WriteAllText(Path.Combine(captureDir,"state.json"),JsonUtility.ToJson(new Snapshot{frame=frame,elapsed=Time.time-started,playerHealth=Player.Health,stamina=Player.Stamina,bossHealth=Boss.Health,bossState=Boss.StateLabel,headExposed=Boss.HeadExposed,swings=Player.Swings,dodges=Player.Dodges,hitsTaken=Player.HitsTaken,dodgedHits=Player.DodgedHits,width=Screen.width,height=Screen.height},true));
    }
    [Serializable]class Snapshot{public int frame,swings,dodges,hitsTaken,dodgedHits,width,height;public float elapsed,playerHealth,stamina,bossHealth;public string bossState;public bool headExposed;}
    void OnApplicationQuit(){if(captureDir!=null&&frameMs.Count>0){frameMs.Sort();File.WriteAllText(Path.Combine(captureDir,"frame-times.json"),JsonUtility.ToJson(new FrameReport{samples=frameMs.Count,p50=frameMs[frameMs.Count/2],p95=frameMs[(int)(frameMs.Count*.95f)],p99=frameMs[(int)(frameMs.Count*.99f)],width=Screen.width,height=Screen.height,note="Native gameplay unscaled frame times. Shared-GPU contamination must be checked externally; not a GPU timing measurement."},true));}}
    [Serializable]class FrameReport{public int samples,width,height;public float p50,p95,p99;public string note;}
    void Styles(){if(label!=null)return;label=new GUIStyle(GUI.skin.label){fontSize=17};label.normal.textColor=new Color(.9f,.88f,.8f);title=new GUIStyle(label){fontSize=32,alignment=TextAnchor.MiddleCenter};small=new GUIStyle(label){fontSize=12};}
    void OnGUI(){
        Styles();float sx=Screen.width/1280f,sy=Screen.height/720f;GUI.matrix=Matrix4x4.Scale(new Vector3(sx,sy,1));
        Bar(38,36,270,15,Player.Health/100,new Color(.54f,.12f,.11f));Bar(38,58,235,8,Player.Stamina/100,new Color(.44f,.59f,.36f));
        GUI.Label(new Rect(38,75,300,28),"✦  "+Player.Flasks+" ember draughts",small);
        GUI.Label(new Rect(935,30,315,24),"VEYR  /  THE CINDER WARDEN",small);
        GUI.Label(new Rect(935,50,315,24),"Early playable · temporary character art",small);
        GUI.Label(new Rect(330,603,620,28),"V E Y R ,   T H E   C I N D E R   W A R D E N",new GUIStyle(label){alignment=TextAnchor.MiddleCenter});
        Bar(230,639,820,13,Boss.Health/Boss.MaxHealth,new Color(.58f,.19f,.12f));
        for(int i=0;i<4;i++){float v=Boss.LegStagger!=null?Boss.LegStagger[i]/100f:0;Bar(450+i*98,665,85,4,v,new Color(.82f,.59f,.25f));}
        GUI.Label(new Rect(380,681,520,20),Boss.HeadExposed?"THE CROWN IS EXPOSED  —  STRIKE THE HEAD":Boss.StateLabel,new GUIStyle(small){alignment=TextAnchor.MiddleCenter});
        GUI.Label(new Rect(30,680,350,25),"WASD · J / LMB sword · Space dodge · Q heal",small);
        GUI.Label(new Rect(930,680,350,25),"RMB look · Tab lock · wheel distance",small);
        if(Time.time-started<8){GUI.Label(new Rect(350,190,580,50),"THE DROWNED CATHEDRAL",title);GUI.Label(new Rect(350,235,580,30),"Break a leg's balance. Reach the fallen crown.",new GUIStyle(label){alignment=TextAnchor.MiddleCenter});}
        if(Player.IsDead||Boss.IsDead){GUI.color=new Color(0,0,0,.7f);GUI.DrawTexture(new Rect(0,270,1280,160),Texture2D.whiteTexture);GUI.color=Color.white;GUI.Label(new Rect(200,285,880,70),Player.IsDead?"YOU FELL":"CINDER EXTINGUISHED",title);GUI.Label(new Rect(200,355,880,40),"Press R to rise again",new GUIStyle(label){alignment=TextAnchor.MiddleCenter});}
        if(hurtFlash>0){GUI.color=new Color(.55f,0,0,hurtFlash*.45f);GUI.DrawTexture(new Rect(0,0,1280,720),Texture2D.whiteTexture);GUI.color=Color.white;}
    }
    static void Bar(float x,float y,float w,float h,float value,Color c){GUI.color=new Color(.02f,.025f,.025f,.85f);GUI.DrawTexture(new Rect(x-2,y-2,w+4,h+4),Texture2D.whiteTexture);GUI.color=new Color(.22f,.19f,.13f);GUI.DrawTexture(new Rect(x,y,w,h),Texture2D.whiteTexture);GUI.color=c;GUI.DrawTexture(new Rect(x,y,w*Mathf.Clamp01(value),h),Texture2D.whiteTexture);GUI.color=Color.white;}
}
