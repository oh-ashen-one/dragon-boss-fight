using UnityEngine;

public sealed class PlayerCombat : MonoBehaviour
{
    public float Health { get; private set; } = 100;
    public float Stamina { get; private set; } = 100;
    public int Flasks { get; private set; } = 4;
    public bool IsDead => Health <= 0;
    public bool Invulnerable => dodgeTime > .08f && dodgeTime < .44f;
    public bool LockedOn { get; private set; }
    public DragonBoss Boss;
    public Camera View;
    public string ActionLabel { get; private set; } = "Ready";
    public int Dodges, Swings, HitsTaken, DodgedHits;
    public bool ReplayEnabled;
    Vector3 replayMove; bool replayAttack,replayDodge,replayHeal;
    public void SetReplayInput(Vector3 worldMove,bool attack,bool dodge,bool heal){replayMove=worldMove;replayAttack=attack;replayDodge=dodge;replayHeal=heal;}
    CharacterController controller;
    Transform visual, swordPivot, leftLeg, rightLeg;
    TrailRenderer trail;
    float attackTime=-1, dodgeTime=-1, healTime=-1, regenDelay, hurtTime, bufferedAttack;
    int swingId;
    Vector3 dodgeDir;
    bool hitSent, healed;

    public void Initialize()
    {
        controller=gameObject.AddComponent<CharacterController>();
        controller.height=1.9f; controller.radius=.34f; controller.center=Vector3.up*.96f;
        controller.stepOffset=.25f; controller.slopeLimit=45;
        visual=new GameObject("TEMP Knight — replace with approved Tripo asset").transform;
        visual.SetParent(transform,false);
        var steel=Mat("Weathered silver",new Color(.25f,.31f,.35f),.8f);
        var dark=Mat("Dark cloth",new Color(.06f,.08f,.09f),.1f);
        var gold=Mat("Old brass",new Color(.55f,.35f,.12f),.65f);
        Part("Breastplate",PrimitiveType.Capsule,new Vector3(0,1.22f,0),new Vector3(.65f,.48f,.4f),steel,visual);
        Part("Helm",PrimitiveType.Sphere,new Vector3(0,1.91f,0),new Vector3(.43f,.49f,.43f),steel,visual);
        Part("Visor",PrimitiveType.Cube,new Vector3(0,1.92f,.22f),new Vector3(.34f,.04f,.04f),dark,visual);
        for(int i=-1;i<=1;i+=2){
            Part("Pauldron",PrimitiveType.Sphere,new Vector3(i*.4f,1.5f,0),new Vector3(.4f,.28f,.42f),steel,visual);
            Part("Arm",PrimitiveType.Capsule,new Vector3(i*.4f,1.12f,.04f),new Vector3(.2f,.32f,.2f),steel,visual);
        }
        leftLeg=Part("Left greave",PrimitiveType.Capsule,new Vector3(-.19f,.5f,0),new Vector3(.24f,.42f,.26f),steel,visual);
        rightLeg=Part("Right greave",PrimitiveType.Capsule,new Vector3(.19f,.5f,0),new Vector3(.24f,.42f,.26f),steel,visual);
        Part("Tabard",PrimitiveType.Cube,new Vector3(0,.85f,-.1f),new Vector3(.54f,.65f,.16f),dark,visual);
        swordPivot=new GameObject("Sword grip").transform;swordPivot.SetParent(visual,false);swordPivot.localPosition=new Vector3(.46f,1.16f,.2f);
        Part("Grip",PrimitiveType.Cylinder,Vector3.zero,new Vector3(.07f,.17f,.07f),dark,swordPivot);
        Part("Guard",PrimitiveType.Cube,new Vector3(0,.18f,0),new Vector3(.43f,.06f,.1f),gold,swordPivot);
        Part("Blade",PrimitiveType.Cube,new Vector3(0,.87f,0),new Vector3(.1f,1.35f,.045f),steel,swordPivot);
        var tip=new GameObject("Sword trail");tip.transform.SetParent(swordPivot,false);tip.transform.localPosition=Vector3.up*1.5f;
        trail=tip.AddComponent<TrailRenderer>();trail.time=.16f;trail.startWidth=.17f;trail.endWidth=0;trail.minVertexDistance=.03f;
        trail.material=new Material(Shader.Find("Sprites/Default"));trail.startColor=new Color(1,.77f,.4f,.75f);trail.endColor=new Color(1,.4f,.1f,0);trail.emitting=false;
    }
    static Material Mat(string n,Color c,float metal){var m=new Material(Shader.Find("Standard"));m.name=n;m.color=c;m.SetFloat("_Metallic",metal);m.SetFloat("_Glossiness",.48f);return m;}
    static Transform Part(string n,PrimitiveType p,Vector3 pos,Vector3 scale,Material m,Transform parent){var g=GameObject.CreatePrimitive(p);g.name=n;g.transform.SetParent(parent,false);g.transform.localPosition=pos;g.transform.localScale=scale;g.GetComponent<Renderer>().sharedMaterial=m;Destroy(g.GetComponent<Collider>());return g.transform;}
    void Update()
    {
        if(!controller||!View)return;
        float dt=Time.deltaTime;regenDelay-=dt;hurtTime-=dt;bufferedAttack-=dt;
        if(Input.GetKeyDown(KeyCode.Tab))LockedOn=!LockedOn;
        if(IsDead){ActionLabel="Fallen";visual.localRotation=Quaternion.Slerp(visual.localRotation,Quaternion.Euler(0,0,85),dt*5);trail.emitting=false;return;}
        if(Boss&&Boss.IsDead){ActionLabel="Victory";trail.emitting=false;return;}
        Vector3 forward=View.transform.forward;forward.y=0;forward.Normalize();
        Vector3 right=View.transform.right;right.y=0;right.Normalize();
        Vector3 movement=Vector3.ClampMagnitude(forward*Input.GetAxisRaw("Vertical")+right*Input.GetAxisRaw("Horizontal"),1);
        if(ReplayEnabled)movement=Vector3.ClampMagnitude(replayMove,1);
        bool attackPressed=ReplayEnabled?replayAttack:Input.GetMouseButtonDown(0)||Input.GetKeyDown(KeyCode.J);
        bool dodgePressed=ReplayEnabled?replayDodge:Input.GetKeyDown(KeyCode.Space);
        bool healPressed=ReplayEnabled?replayHeal:Input.GetKeyDown(KeyCode.Q);
        replayAttack=replayDodge=replayHeal=false;
        if(attackPressed)bufferedAttack=.2f;
        bool free=attackTime<0&&dodgeTime<0&&healTime<0;
        if(free&&dodgePressed&&Stamina>=25){dodgeTime=0;Stamina-=25;regenDelay=.65f;dodgeDir=movement.sqrMagnitude>.01f?movement:transform.forward;Dodges++;}
        else if(free&&healPressed&&Flasks>0&&Health<100){healTime=0;healed=false;Flasks--;}
        else if(free&&bufferedAttack>0&&Stamina>=22){attackTime=0;Stamina-=22;regenDelay=.75f;hitSent=false;swingId++;Swings++;bufferedAttack=0;CombatAudio.PlaySword();}
        float speed=5.8f;
        if(attackTime>=0){
            attackTime+=dt;speed=1.4f;ActionLabel="Sword";
            float pose=Mathf.Clamp01(attackTime/.67f);
            swordPivot.localRotation=Quaternion.Euler(Mathf.Sin(pose*Mathf.PI)*-70,Mathf.Lerp(-105,100,Mathf.SmoothStep(0,1,pose)),35);
            trail.emitting=attackTime>.17f&&attackTime<.39f;
            if(attackTime>=.23f&&!hitSent){hitSent=true;if(Boss)Boss.ReceiveSword(transform.position,transform.forward,swingId);}
            if(attackTime>.65f){attackTime=-1;trail.emitting=false;}
        }else swordPivot.localRotation=Quaternion.Slerp(swordPivot.localRotation,Quaternion.Euler(20,0,-15),dt*12);
        if(dodgeTime>=0){dodgeTime+=dt;ActionLabel="Dodge";movement=dodgeDir;speed=11.8f;visual.localRotation=Quaternion.Euler(Mathf.Clamp01(dodgeTime/.58f)*360,0,0);if(dodgeTime>.58f){dodgeTime=-1;visual.localRotation=Quaternion.identity;}}
        else if(healTime>=0){healTime+=dt;ActionLabel="Healing";speed=1.2f;if(healTime>=.85f&&!healed){Health=Mathf.Min(100,Health+55);healed=true;}if(healTime>1.25f)healTime=-1;}
        else if(attackTime<0)ActionLabel="Ready";
        if(hurtTime>0)speed*=.45f;
        Vector3 facing=movement;
        if(LockedOn&&Boss){facing=Boss.transform.position-transform.position;facing.y=0;}
        if(facing.sqrMagnitude>.0001f&&attackTime<.15f&&dodgeTime<0)transform.rotation=Quaternion.Slerp(transform.rotation,Quaternion.LookRotation(facing),dt*13);
        controller.Move((movement*speed+Vector3.down*9)*dt);
        var pos=transform.position;if(new Vector2(pos.x,pos.z).magnitude>36){pos=new Vector3(pos.x,0,pos.z).normalized*36;controller.enabled=false;transform.position=pos;controller.enabled=true;}
        if(regenDelay<=0&&attackTime<0&&dodgeTime<0&&healTime<0)Stamina=Mathf.Min(100,Stamina+29*dt);
        float walk=Mathf.Sin(Time.time*12)*movement.magnitude*26;leftLeg.localRotation=Quaternion.Euler(walk,0,0);rightLeg.localRotation=Quaternion.Euler(-walk,0,0);
    }
    public void TakeDamage(float damage,Vector3 source)
    {
        if(IsDead||Boss&&Boss.IsDead)return;
        if(Invulnerable){DodgedHits++;return;}
        if(hurtTime>0)return;
        Health=Mathf.Max(0,Health-damage);HitsTaken++;hurtTime=.65f;healTime=-1;
        if(controller){var away=transform.position-source;away.y=0;controller.Move(away.normalized*.45f);}
        if(Encounter.Instance)Encounter.Instance.FlashDamage();
    }
}
