using UnityEngine;
using System;
using System.IO;
using System.Collections;
using System.Collections.Generic;

/// <summary>Captures actual native backbuffer frames; timestamps preserve real gameplay pacing.</summary>
public sealed class NativeRecorder:MonoBehaviour
{
    [Serializable]class Frame{public string file;public double seconds;}
    [Serializable]class Recording{public string method="Native backbuffer, real time; variable frame timestamps. Not a performance benchmark.";public int width,height;public List<Frame> frames=new List<Frame>();}
    Recording recording=new Recording();string directory;double start;int index;
    public void Initialize(string output){directory=Path.GetFullPath(output);Directory.CreateDirectory(directory);recording.width=Screen.width;recording.height=Screen.height;start=Time.realtimeSinceStartupAsDouble;StartCoroutine(Record());}
    IEnumerator Record(){while(true){yield return new WaitForEndOfFrame();if(directory==null)yield break;double t=Time.realtimeSinceStartupAsDouble-start;string file="frame-"+(index++).ToString("D06")+".jpg";var texture=ScreenCapture.CaptureScreenshotAsTexture();File.WriteAllBytes(Path.Combine(directory,file),texture.EncodeToJPG(85));Destroy(texture);recording.frames.Add(new Frame{file=file,seconds=t});if(index%15==0)Save();yield return new WaitForSecondsRealtime(.09f);}}
    void Save(){if(directory!=null)File.WriteAllText(Path.Combine(directory,"frames.json"),JsonUtility.ToJson(recording,true));}
    void OnApplicationQuit(){Save();}
    void OnDestroy(){Save();}
}
