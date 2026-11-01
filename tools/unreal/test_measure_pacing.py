import unittest

from measure_pacing import measure


def event(time, count, health, damage=0, stage='combat'):
    return dict(encounterWallSeconds=time,swordContacts=count,bossHealth=health,
                bossMaxHealth=100,lastSwordDamage=damage,lastHitRegion=0,
                dragonState='Dead' if health==0 else 'Idle',replayStage=stage)


class PacingEvidenceTests(unittest.TestCase):
    def evidence(self, events):
        return dict(mode='victory',finalWrite=True,sourceId='fixture',passed=True,
                    terminalWallSeconds=30,events=events)

    def test_deduplicates_snapshots_caps_overkill_and_excludes_restart(self):
        result=measure(self.evidence([event(0,0,100),event(5,1,70,30),event(6,1,70,30),
            event(30,2,0,90),event(1,1,60,40,'restart_verification')]))
        self.assertEqual(len(result['hits']),2)
        self.assertEqual(result['firstHitActiveSeconds'],5)
        self.assertEqual(result['longestNoDamageGap']['seconds'],25)
        self.assertEqual(result['largestFourSecondHealthLossFraction'],.7)

    def test_missing_contact_is_not_reconstructed(self):
        with self.assertRaisesRegex(ValueError,'Missing damage'):
            measure(self.evidence([event(0,0,100),event(8,2,20,40)]))

    def test_nonfinite_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Invalid encounter clock'):
            measure(self.evidence([event(0,0,100),event(float('nan'),1,60,40)]))


if __name__=='__main__':unittest.main()
