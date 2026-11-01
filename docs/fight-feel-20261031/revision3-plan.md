# Fight feedback revision 3 — candidate

Revision 2 clearly exposed more of the knight and struck limb. The blind Opus report chose it, but its gate paragraph contradicted its preference, and its impact score fell because the small marker weakened the head-hit cue. No acceptance claimed.

Revision 3 keeps the revision-2 camera and marker, and restores the revision-1 point-light highlight on **existing character-only channel 1**, with indirect-light contribution zero. Knight, sword, cup and dragon already receive channel 1; arena/floor meshes do not. No receiver channels are modified. Channel 2 was found to be reserved for the dragon rim light, so an early build (`package-20261101T050452Z`) was deliberately stopped before any launch; the corrected build uses `package-20261101T050648Z`.

Comparison flags: disabled original = `-VeyrFightFeelOff`; revision 1 = `-VeyrFightFeelLegacy`; revision 2 = `-VeyrFightFeelMarkerOnly`; default = revision 3. Replay evidence records the revision. No health, damage, source animation, effect weight or hit-stop duration change.

Pending: compile/package, rendered receiver isolation, native replay checks and an unambiguous independent blind quality verdict. Owner playtest remains separate.
