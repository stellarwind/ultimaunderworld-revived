"""Compare the actual swimming camera effect with its original, unenhanced path."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

from weaponswaycheck import function

ROOT = Path(__file__).resolve().parents[1]


def main():
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    if not cc:
        raise SystemExit("swimmingcheck: a C11 compiler is required")
    effect = function((ROOT / "src/motion/PLAYMOVE.C").read_text(), "parse_effect")
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "portgame.h"
#include "sys/enhance.h"
#define far
#define MS_LAVA 2
#define MS_FLOAT 8
#define MS_SHAKE 32
#define MS_TREMOR 64
#define DMG_FIRE 1
static struct { unsigned char motion_state, swim_count; } data, *player=&data;
static struct { int speed; } PN;
static int pFPS[1]={512}, doMod, damage, rng_calls;
static int16_t playerMod[4];
static unsigned char tsteps, combEfflen, tremEfflen;
static signed char rorEffect[16]={-4,-3,-2,-1,0,1,2,3,4,3,2,1,0,-1,-2,-3};
static int DragonSkinBoots_dseg_5c99_1B01, ThePlayer;
static uint32_t seed;
uint32_t enhance_on;
static int test_rand(void) { rng_calls++; seed=seed*1103515245u+12345u; return (seed>>16)&32767; }
#define rand test_rand
static void editchng(int n) { (void)n; }
static void damage_item(int a,long b,int c,int d,int e,int f) {
    (void)a;(void)b;(void)c;(void)d;(void)e;(void)f; damage++;
}
static int test_abs(int x) { return x<0 ? -x : x; }
#define abs test_abs
'''
    code += '\n#define __TURBOC__\n' + effect.replace("parse_effect(", "original_effect(")
    code += '\n#undef __TURBOC__\n' + effect
    code += r'''
static void setup(int state,int depth,int speed,int phase,int enabled) {
    player->motion_state=state;player->swim_count=depth;PN.speed=speed;tsteps=phase;
    enhance_on=enabled ? 1u<<ENH_STEADY_SWIMMING : 0;
    combEfflen=24;tremEfflen=40;seed=123;damage=0;rng_calls=0;
    for(int i=0;i<4;i++) playerMod[i]=0;
}
int main(void) {
    int states[]={0,1,2,8,16,32,64,33,65,97,3,9};
    for(unsigned s=0;s<sizeof states/sizeof states[0];s++)
    for(int depth=0;depth<=140;depth+=16)
    for(int speed=0;speed<=512;speed+=128)
    for(int phase=0;phase<256;phase+=8) {
        int expected[4],calls,hit,swim_roll=0;
        uint32_t original_seed;
        setup(states[s],depth,speed,phase,0);original_effect();
        for(int i=0;i<4;i++) expected[i]=playerMod[i];
        original_seed=seed;calls=rng_calls;hit=damage;
        int state=player->motion_state,combat=combEfflen,tremor=tremEfflen;
        setup(states[s],depth,speed,phase,0);parse_effect();
        for(int i=0;i<4;i++) assert(playerMod[i]==expected[i]);
        assert(seed==original_seed && rng_calls==calls && damage==hit);
        if((states[s]&0x11) && depth>0x50) {
            /* Isolate only the swimming component; subsequent effects must survive. */
            setup(1,depth,speed,phase,0);original_effect();
            expected[1]-=playerMod[1];expected[2]-=playerMod[2];
            if(speed==0) swim_roll=playerMod[3];
            expected[3]-=swim_roll;
        }
        setup(states[s],depth,speed,phase,1);parse_effect();
        assert(doMod==1);
        for(int i=0;i<4;i++) assert(playerMod[i]==expected[i]);
        assert(seed==original_seed && rng_calls==calls && damage==hit);
        assert(player->motion_state==state && combEfflen==combat && tremEfflen==tremor);
    }
    puts("swimmingcheck: original path, bobbing, moving roll, RNG, lava damage and independent shakes preserved; random swimming jolts removed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="uw1-swimming-") as work:
        work = Path(work)
        source = work / "check.c"
        source.write_text(code)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I",
                        str(ROOT / "src/port"), "-I", str(ROOT.parent / "exhume/runtime/port"),
                        str(source), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
