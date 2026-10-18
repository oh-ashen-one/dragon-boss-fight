using UnityEngine;

/// <summary>Player-led orbit with restrained, smoothly blended giant-boss framing.</summary>
public sealed class CombatCamera : MonoBehaviour
{
    public PlayerCombat Player;
    public DragonBoss Boss;
    float yaw, preferredPitch = 20, preferredDistance = 8;
    float currentPitch = 20, currentDistance = 8, pitchVelocity, distanceVelocity, yawVelocity;
    float lastManualLook = -100, nextAnatomyRefresh;
    Vector3 positionVelocity, anchorVelocity, smoothedAnchor;
    Transform torso;
    bool initialized;
    readonly RaycastHit[] obstructionHits = new RaycastHit[32];
    OccludedPlayerSilhouette silhouette;

    void LateUpdate()
    {
        if (!Player) return;
        float dt = Mathf.Min(Time.deltaTime, .1f);
        if (!silhouette)
        {
            silhouette = GetComponent<OccludedPlayerSilhouette>();
            if (!silhouette) silhouette = gameObject.AddComponent<OccludedPlayerSilhouette>();
        }
        silhouette.Player = Player; silhouette.Boss = Boss;
        if (Input.GetKeyDown(KeyCode.Escape)) { Cursor.lockState = CursorLockMode.None; Cursor.visible = true; }
        bool manual = Input.GetMouseButton(1);
        if (manual)
        {
            yaw += Input.GetAxis("Mouse X") * 3;
            preferredPitch = Mathf.Clamp(preferredPitch - Input.GetAxis("Mouse Y") * 2, 4, 65);
            lastManualLook = Time.time;
            yawVelocity = 0;
        }
        preferredDistance = Mathf.Clamp(preferredDistance - Input.mouseScrollDelta.y, 5, 14);
        float assistance = Mathf.SmoothStep(0, 1, Mathf.Clamp01((Time.time - lastManualLook - .55f) / .7f));
        Vector3 playerPosition = Player.transform.position;
        Vector3 head = playerPosition + transform.forward * 8;
        Vector3 body = head;
        float proximity = 0;
        bool hasBoss = Boss && !Boss.IsDead;
        if (hasBoss)
        {
            if (Time.time >= nextAnatomyRefresh || !torso || !torso.gameObject.activeInHierarchy)
            {
                nextAnatomyRefresh = Time.time + .8f;
                torso = null;
                foreach (var candidate in Boss.GetComponentsInChildren<Transform>(true))
                    if (candidate.gameObject.activeInHierarchy && (candidate.name == "body" || candidate.name == "Basalt torso"))
                    { torso = candidate; if (candidate.name == "body") break; }
            }
            body = torso ? torso.position : Boss.transform.position + Vector3.up * 3.3f;
            head = Boss.HeadTarget ? Boss.HeadTarget.position : body;
            Vector3 toBody = body - playerPosition; toBody.y = 0;
            Vector3 toHead = head - playerPosition; toHead.y = 0;
            float nearest = Mathf.Min(toBody.magnitude, toHead.magnitude + 1.5f);
            proximity = 1 - Mathf.InverseLerp(4, 13, nearest);
            if (Player.LockedOn && !manual)
            {
                // Tracking blends into the real torso at contact range, so the
                // head crossing over the knight cannot flip camera yaw 180°.
                float headWeight = Boss.HeadExposed ? .85f : .4f;
                headWeight *= Mathf.InverseLerp(1.8f, 5, toHead.magnitude);
                Vector3 toward = Vector3.Lerp(body, head, headWeight) - playerPosition;
                toward.y = 0;
                if (toward.sqrMagnitude > 4)
                {
                    float targetYaw = Mathf.Atan2(toward.x, toward.z) * Mathf.Rad2Deg;
                    targetYaw = Mathf.LerpAngle(yaw, targetYaw, assistance);
                    yaw = Mathf.SmoothDampAngle(yaw, targetYaw, ref yawVelocity, .30f, 95, dt);
                }
            }
        }
        float framing = proximity * assistance;
        float pitchTarget = Mathf.Clamp(preferredPitch + framing * (hasBoss && Boss.HeadExposed ? 12 : 9), 4, 68);
        float distanceTarget = Mathf.Clamp(preferredDistance + framing * 2.2f, 5, 15);
        currentPitch = Mathf.SmoothDamp(currentPitch, pitchTarget, ref pitchVelocity, manual ? .085f : .42f, manual ? 180 : 35, dt);
        currentDistance = Mathf.SmoothDamp(currentDistance, distanceTarget, ref distanceVelocity, .45f, 8, dt);
        Vector3 anchor = playerPosition + Vector3.up * Mathf.Lerp(1.65f, 1.85f, framing);
        if (!initialized) { smoothedAnchor = anchor; initialized = true; }
        smoothedAnchor = Vector3.SmoothDamp(smoothedAnchor, anchor, ref anchorVelocity, .055f, 60, dt);
        Quaternion orbit = Quaternion.Euler(currentPitch, yaw, 0);
        Vector3 right = orbit * Vector3.right;
        Vector3 desired = smoothedAnchor - orbit * Vector3.forward * currentDistance + right * framing * .4f;
        Vector3 cameraRay = desired - smoothedAnchor;
        float safeDistance = cameraRay.magnitude;
        int hits = Physics.SphereCastNonAlloc(smoothedAnchor, .27f, cameraRay.normalized, obstructionHits,
            safeDistance, ~0, QueryTriggerInteraction.Ignore);
        for (int i = 0; i < hits; i++)
        {
            var collider = obstructionHits[i].collider;
            if (!collider || collider.transform.IsChildOf(Player.transform) ||
                Boss && collider.transform.IsChildOf(Boss.transform)) continue;
            safeDistance = Mathf.Min(safeDistance, Mathf.Max(.8f, obstructionHits[i].distance - .12f));
        }
        desired = smoothedAnchor + cameraRay.normalized * safeDistance;
        desired.y = Mathf.Max(.65f, desired.y);
        transform.position = Vector3.SmoothDamp(transform.position, desired, ref positionVelocity, .11f, 70, dt);
        // A modest shoulder offset retains the knight's pose. No automatic yaw
        // adjustment occurs while the player is fighting without lock-on.
        Vector3 lookPoint = smoothedAnchor + orbit * Vector3.forward * 1.8f + right * framing * .65f;
        if (hasBoss && Player.LockedOn)
            lookPoint.y += Mathf.Clamp((head.y - anchor.y) * .12f, -.2f, .75f) * assistance;
        Quaternion look = Quaternion.LookRotation(lookPoint - transform.position, Vector3.up);
        transform.rotation = Quaternion.Slerp(transform.rotation, look, 1 - Mathf.Exp(-dt * 16));
    }
}
