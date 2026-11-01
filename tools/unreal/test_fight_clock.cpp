#include "VeyrFightClock.h"
#include <cassert>
#include <cmath>

static bool Near(double A,double B){return std::abs(A-B)<1e-8;}

int main()
{
    FVeyrFightClock Clock;
    Clock.Sample(100.,false,false);
    Clock.Sample(110.,true,false);
    assert(Near(Clock.Seconds(110.,false),0.)); // No load/menu time.
    Clock.Sample(111.,true,false);
    Clock.Sample(111.05,true,false); // A 50ms hit-stop still consumes 50ms wall time.
    assert(Near(Clock.Seconds(111.1,false),1.1));

    // Sample the old pause state at both boundaries, as the menu setter does.
    Clock.Sample(111.1,true,false);
    Clock.Sample(115.,true,true);
    Clock.Sample(116.,true,true);
    Clock.Sample(117.,true,false);
    assert(Near(Clock.Seconds(117.,false),2.1));
    Clock.Finish(118.,false);
    assert(Near(Clock.Seconds(200.,false),3.1));
    Clock.Sample(201.,true,false);
    assert(Near(Clock.Seconds(202.,false),3.1)); // Death animation/restart excluded.

    FVeyrFightClock PausedStart;
    PausedStart.Sample(10.,true,true);
    assert(Near(PausedStart.Seconds(20.,true),0.));
    PausedStart.Sample(20.,true,false);
    PausedStart.Sample(21.,true,false);
    PausedStart.Sample(20.5,true,false); // A defensive backward sample adds nothing.
    assert(Near(PausedStart.Seconds(21.,false),1.));
}
