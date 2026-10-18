using UnityEngine;
public sealed class CombatCamera:MonoBehaviour
{
    public PlayerCombat Player; public DragonBoss Boss;
    float yaw, pitch=20, distance=8; Vector3 velocity;
    void LateUpdate(){
        if(!Player)return;
        if(Input.GetKeyDown(KeyCode.Escape)){Cursor.lockState=CursorLockMode.None;Cursor.visible=true;}
        if(Input.GetMouseButton(1)){yaw+=Input.GetAxis("Mouse X")*3;pitch=Mathf.Clamp(pitch-Input.GetAxis("Mouse Y")*2,4,65);}
        distance=Mathf.Clamp(distance-Input.mouseScrollDelta.y,5,14);
        var anchor=Player.transform.position+Vector3.up*1.8f;
        if(Player.LockedOn&&Boss&&!Boss.IsDead&&!Input.GetMouseButton(1)){
            var toward=Boss.HeadTarget?Boss.HeadTarget.position-anchor:Boss.transform.position-anchor;
            yaw=Mathf.LerpAngle(yaw,Mathf.Atan2(toward.x,toward.z)*Mathf.Rad2Deg,Time.deltaTime*3);
        }
        var rotation=Quaternion.Euler(pitch,yaw,0);var desired=anchor-rotation*Vector3.forward*distance;
        // Only environment colliders block the camera; boss visual regions are analytic and do not push it inward.
        if(Physics.SphereCast(anchor,.25f,(desired-anchor).normalized,out var hit,distance,~0,QueryTriggerInteraction.Ignore)){
            if(hit.collider.gameObject!=Player.gameObject)desired=anchor+(desired-anchor).normalized*Mathf.Max(2,hit.distance-.25f);
        }
        desired.y=Mathf.Max(.8f,desired.y);transform.position=Vector3.SmoothDamp(transform.position,desired,ref velocity,.075f);
        transform.rotation=Quaternion.LookRotation(anchor+rotation*Vector3.forward*2-transform.position);
    }
}
