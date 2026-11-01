#pragma once

/** Monotonic wall clock; gameplay time dilation is deliberately not an input. */
struct FVeyrFightClock
{
    void Sample(double Now,bool bEngaged,bool bPaused)
    {
        if(Now<LastSample)Now=LastSample;
        if(!bStarted)
        {
            if(bEngaged&&!bPaused){bStarted=true;Elapsed=0.;}
        }
        else if(bEngaged&&!bPaused&&Terminal<0.)Elapsed+=Now-LastSample;
        LastSample=Now;
    }

    double Seconds(double Now,bool bPaused) const
    {
        if(!bStarted)return 0.;
        if(Terminal>=0.)return Terminal;
        return Elapsed+(!bPaused&&Now>LastSample?Now-LastSample:0.);
    }

    void Finish(double Now,bool bPaused)
    {
        if(bStarted&&Terminal<0.){Terminal=Seconds(Now,bPaused);Elapsed=Terminal;LastSample=Now;}
    }

private:
    bool bStarted=false;
    double LastSample=0.,Elapsed=0.,Terminal=-1.;
};
