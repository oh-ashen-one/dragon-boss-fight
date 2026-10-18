using System;
using UnityEngine;

/// <summary>
/// Original synthesized audio. Every sample is generated here from oscillators
/// and deterministic noise; no recordings, third-party assets, or external files.
/// Sources are pooled, and no Update method or audio-thread allocation is needed.
/// </summary>
public static class CombatAudio
{
    const int SampleRate = 48000;
    const int PoolSize = 14;
    static GameObject host;
    static AudioSource[] sources;
    static double[] started;
    static AudioClip sword, impact, roar, stomp, heal, drone;
    static readonly double[] HealingFrequencies = { 659.255, 880, 987.767, 1318.51 };
    static int variation;

    public static void Initialize()
    {
        if (host) return;
        host = new GameObject("Original synthesized combat audio");
        if (!sword)
        {
            sword = Create("Original sword air and steel", .34f, Sword, .77f);
            impact = Create("Original blade impact", .62f, Impact, .88f);
            roar = Create("Original reliquary dragon roar", 2.85f, Roar, .82f);
            stomp = Create("Original massive stone footfall", 1.40f, Stomp, .9f);
            heal = Create("Original healing chime", 1.65f, Heal, .55f);
            drone = Create("Original cavern harmonic drone", 8, Drone, .7f, true);
        }
        sources = new AudioSource[PoolSize];
        started = new double[PoolSize];
        for (int i = 0; i < PoolSize; i++)
        {
            var go = new GameObject("Combat voice " + (i + 1));
            go.transform.SetParent(host.transform);
            var source = go.AddComponent<AudioSource>();
            source.playOnAwake = false;
            source.loop = false;
            source.dopplerLevel = 0;
            source.rolloffMode = AudioRolloffMode.Logarithmic;
            source.minDistance = 9;
            source.maxDistance = 90;
            source.spread = 50;
            source.priority = 90;
            source.reverbZoneMix = .25f;
            sources[i] = source;
        }
        var ambience = host.AddComponent<AudioSource>();
        ambience.playOnAwake = false;
        ambience.clip = drone;
        ambience.loop = true;
        ambience.spatialBlend = 0;
        ambience.volume = .075f;
        ambience.priority = 220;
        ambience.Play();
    }

    public static void PlaySword() { Initialize(); Play(sword, Vector3.zero, .39f, false, 1.0f); }
    public static void PlayImpact(Vector3 pos) { Initialize(); Play(impact, pos, .64f, true, 1.0f); }
    public static void PlayRoar(Vector3 pos) { Initialize(); Play(roar, pos, .70f, true, .97f); }
    public static void PlayStomp(Vector3 pos) { Initialize(); Play(stomp, pos, .75f, true, .97f); }
    public static void PlayHeal() { Initialize(); Play(heal, Vector3.zero, .38f, false, 1.0f); }

    static void Play(AudioClip clip, Vector3 position, float volume, bool spatial, float pitch)
    {
        int slot = -1;
        double oldest = double.MaxValue;
        for (int i = 0; i < sources.Length; i++)
        {
            if (!sources[i].isPlaying) { slot = i; break; }
            if (started[i] < oldest) { oldest = started[i]; slot = i; }
        }
        AudioSource voice = sources[slot];
        voice.Stop();
        voice.transform.position = position;
        voice.clip = clip;
        voice.spatialBlend = spatial ? .84f : 0;
        voice.volume = volume;
        // Deterministic pitch variation avoids identical repeated sword/foot hits
        // without changing UnityEngine.Random, which gameplay may depend upon.
        variation = (variation + 1) % 7;
        voice.pitch = pitch + (variation - 3) * .013f;
        voice.priority = clip == roar || clip == stomp ? 60 : 90;
        started[slot] = AudioSettings.dspTime;
        voice.Play();
    }

    delegate double Synth(double t, ref NoiseState noise);
    struct NoiseState
    {
        public uint seed;
        public double low, mid, phase;
        public double Next()
        {
            seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5;
            return seed / 2147483648.0 - 1;
        }
        public double Low(double value, double coefficient)
        {
            low += coefficient * (value - low); return low;
        }
        public double Mid(double value, double coefficient)
        {
            mid += coefficient * (value - mid); return mid;
        }
    }

    static AudioClip Create(string name, float seconds, Synth synth, float peak, bool seamless = false)
    {
        int count = Mathf.RoundToInt(SampleRate * seconds);
        var data = new float[count];
        var state = new NoiseState { seed = 0xB7471C53u };
        double max = .001;
        for (int i = 0; i < count; i++)
        {
            double t = i / (double)SampleRate;
            double value = synth(t, ref state);
            if (!seamless)
            {
                // Millisecond ramps remove discontinuities even when a transient
                // starts immediately. Tail fade is independent of synthesis shape.
                double attack = Math.Min(1, t / .002);
                double release = Math.Min(1, (seconds - t) / .045);
                value *= attack * release;
            }
            data[i] = (float)value;
            max = Math.Max(max, Math.Abs(value));
        }
        float scale = (float)(peak / max);
        for (int i = 0; i < count; i++) data[i] *= scale;
        var clip = AudioClip.Create(name, count, 1, SampleRate, false);
        clip.SetData(data, 0);
        return clip;
    }

    const double Tau = Math.PI * 2;
    static double Sin(double frequency, double t) { return Math.Sin(Tau * frequency * t); }
    static double Exp(double t, double rate) { return Math.Exp(-t * rate); }

    static double Sword(double t, ref NoiseState n)
    {
        double raw = n.Next();
        double band = n.Mid(raw, .30) - n.Low(raw, .055);
        double sweep = Math.Exp(-Math.Pow((t - .11) / .065, 2));
        double air = band * sweep * 1.7;
        double steel = (Sin(1741, t) + .43 * Sin(2633, t)) * .055 * Exp(t, 13);
        return air + steel;
    }

    static double Impact(double t, ref NoiseState n)
    {
        double raw = n.Next();
        double bodyNoise = n.Low(raw, .038);
        // Integrated chirp: starts around 138 Hz and settles into a low body.
        double phase = Tau * (48 * t + 4.5 * (1 - Exp(t, 20)));
        double body = Math.Sin(phase) * Exp(t, 10) * .63;
        double crack = (raw - n.Mid(raw, .14)) * Exp(t, 100) * .58;
        double grit = bodyNoise * Exp(t, 8) * .7;
        double blade = (Sin(851, t) + Sin(1337, t) * .3) * Exp(t, 25) * .065;
        return body + crack + grit + blade;
    }

    static double Stomp(double t, ref NoiseState n)
    {
        double raw = n.Next();
        double rumble = n.Low(raw, .013);
        double gravel = n.Mid(raw, .12) - rumble;
        double phase = Tau * (31 * t + 4.3 * (1 - Exp(t, 13)));
        double sub = Math.Sin(phase) * Exp(t, 4.8) * .76;
        double knock = Sin(118, t) * Exp(t, 24) * .18;
        double debris = gravel * Exp(t, 6.2) * .46;
        double reflection = t > .11 ? Sin(47, t - .11) * Exp(t - .11, 6) * .13 : 0;
        return sub + knock + rumble * Exp(t, 2.8) * 1.05 + debris + reflection;
    }

    static double Roar(double t, ref NoiseState n)
    {
        double raw = n.Next();
        double breath = n.Mid(raw, .15) - n.Low(raw, .022);
        double attack = Math.Min(1, t / .27);
        double release = Math.Max(0, Math.Min(1, (2.85 - t) / .9));
        double envelope = attack * release * (.82 + .18 * Sin(1.4, t));
        double fundamental = 40 + 19 * Math.Sin(Math.Min(1, t / 2.85) * Math.PI) + 2.4 * Sin(9, t);
        n.phase += Tau * fundamental / SampleRate;
        double throat = Math.Sin(n.phase) * .38 + Math.Sin(n.phase * 2) * .19 + Math.Sin(n.phase * 3) * .11;
        // Non-integer bands and slow tremor avoid a clean musical oscillator.
        double rasp = Math.Sin(n.phase * 4.13 + 1.9 * Sin(17, t)) * .07;
        double formant = breath * (.75 + .25 * Sin(31, t)) * .85;
        return (throat + rasp + formant) * envelope;
    }

    static double Heal(double t, ref NoiseState n)
    {
        double result = 0;
        for (int i = 0; i < HealingFrequencies.Length; i++)
        {
            double noteTime = t - i * .085;
            if (noteTime < 0) continue;
            double envelope = (1 - Exp(noteTime, 100)) * Exp(noteTime, 3.8 + i * .35);
            result += (Sin(HealingFrequencies[i], noteTime) + .14 * Sin(HealingFrequencies[i] * 2.003, noteTime)) * envelope * .20;
        }
        return result + Sin(164.814, t) * (1 - Exp(t, 25)) * Exp(t, 5) * .08;
    }

    static double Drone(double t, ref NoiseState n)
    {
        // All frequencies and modulation are integer multiples of 1/8 Hz,
        // yielding a continuous eight-second loop without a click or crossfade.
        double slow = .72 + .12 * Sin(.125, t) + .08 * Sin(.25, t);
        double low = Sin(36, t) * .35 + Sin(54, t) * .14 + Sin(72.125, t) * .12;
        double air = Sin(180.25, t) * .025 + Sin(287.375, t) * .014;
        return (low + air) * slow;
    }
}
