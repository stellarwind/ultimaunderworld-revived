"""Check the actual sway helper and PANELS.C draw path without original game assets."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(text, name):
    start = text.index("void far " + name + "(")
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    cc = os.environ.get("CC") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        raise SystemExit("weaponswaycheck: a C11 compiler is required")
    code = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "portgame.h"
#include "sys/enhance.h"
#define far
#define SCR_WEAPON 8
#define WEAP_SHEATHED 6
#define WEAP_READY 4
#define WEAP_DRAWING 3
#define WEAP_SHEATHING 5
#define ICON_3DWIN 0
#define ems_frame 0
#define MK_FP(a,b) page
static uint32_t tick, seed;
static uint32_t *Time=&tick;
uint32_t enhance_on;
static int rng_calls, drawn_x;
static unsigned char page[65536];
static unsigned char *wbuf;
static int wxo,wfo,Transparency,weap_frame,last_weap=0,ShowStupidFirstPersonWeapon=1;
static unsigned char setting[9],weap_x[28],weap_y[28];
static int weap_offs[29],obj_inpage1,seg051_C377;
static struct { int speed; } PN;
struct Bitmap { unsigned char data[3]; };
static int test_rand(void) { rng_calls++; seed=seed*1103515245u+12345u; return (seed>>16)&32767; }
#define rand test_rand
static void seg012_10F(int a,int b) { (void)a; (void)b; }
static unsigned char *grs_unpack(struct Bitmap *b) { return (unsigned char *)b; }
static void fbshow(unsigned char *p,int x,int y,int w,int h) {
    (void)p;(void)y;assert(w==10 && h==10);drawn_x=x;
}
static void pic_to_fbuf(int a,int b,int c) { (void)a;(void)b;(void)c; }
"""
    code += '\n#include "' + (ROOT / "src/port/ui/weapon_sway.c").as_posix() + '"\n'
    panels = (ROOT / "src/ui/PANELS.C").read_text()
    code += function(panels, "jiggle_weapon") + "\n" + function(panels, "do_fbuf_bms")
    code += r"""
static void reset_sway(void) { port_weapon_sway(0,0,0); }
static void reset_draw(int enhanced) {
    memset(setting,0,sizeof setting);setting[8]=WEAP_READY;
    memset(weap_x,100,sizeof weap_x);memset(weap_y,50,sizeof weap_y);
    memset(page,0,sizeof page);page[1]=page[2]=10;
    PN.speed=600;wxo=0;wfo=1;weap_frame=-1;seed=1;rng_calls=0;
    enhance_on=enhanced ? 1u<<ENH_SMOOTH_WEAPON_SWAY : 0;
    reset_sway();
}
int main(void) {
    int baseline[512],i,step,how,last,x;
    uint32_t seeds[80];int offsets[80],calls[80];
    for(how=1;how<=2;how++) {
        reset_sway();
        for(i=0;i<512;i++) baseline[i]=port_weapon_sway(how,0,(unsigned)i);
        for(step=2;step<=16;step*=2) {
            reset_sway();
            for(i=0;i<512;i+=step) assert(port_weapon_sway(how,0,(unsigned)i)==baseline[i]);
        }
        reset_sway();last=0;
        for(i=0;i<512;i+=8) {
            x=port_weapon_sway(how,0,(unsigned)i);
            assert(x>=-(how==1?4:9) && x<=(how==1?4:9));
            assert(abs(x-last)<=(how==1?2:4));last=x;
        }
    }
    reset_sway();port_weapon_sway(2,0,0);x=port_weapon_sway(2,0,100);
    for(i=0;i<100;i++) assert(port_weapon_sway(2,0,100)==x);
    assert(port_weapon_sway(0,0,101)==0);
    assert(port_weapon_sway(2,0,102)==0);
    assert(port_weapon_sway(2,1,120)==0);
    assert(port_weapon_sway(2,0,121)==0);
    assert(port_weapon_sway(2,0,1000)==0);
    reset_sway();port_weapon_sway(2,0,UINT32_MAX-15u);
    assert(port_weapon_sway(2,0,16)==9);
    reset_draw(0);
    for(i=0;i<80;i++) {
        tick=(unsigned)i*8;do_fbuf_bms();seeds[i]=seed;offsets[i]=wxo;calls[i]=rng_calls;
        assert(drawn_x==100+wxo && obj_inpage1==0xFF);
    }
    reset_draw(1);
    for(i=0;i<80;i++) {
        tick=(unsigned)i*8;do_fbuf_bms();
        assert(seed==seeds[i] && wxo==offsets[i] && rng_calls==calls[i] && wfo==1);
        assert(drawn_x>=91 && drawn_x<=109 && Transparency==0);
    }
    /* A swing uses the unshifted original weapon frame, with no combat-state changes. */
    setting[8]=0;weap_frame=2;do_fbuf_bms();
    assert(drawn_x==100 && weap_frame==2 && setting[8]==0 && wxo==0);
    PN.speed=0;setting[8]=WEAP_READY;weap_frame=-1;do_fbuf_bms();assert(drawn_x==100);
    puts("weaponswaycheck: clock/frame-rate independence, smooth bounds, pause, idle/swing reset, wraparound, original RNG/state and disabled draw path passed");
    return 0;
}
"""
    with tempfile.TemporaryDirectory(prefix="uw1-weapon-sway-") as work:
        work = Path(work)
        (work / "check.c").write_text(code)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        subprocess.run([cc,"-std=gnu11","-Wall","-Wextra","-Werror","-I",str(ROOT / "src/port"),
                        "-I",str(ROOT.parent / "exhume/runtime/port"),str(work / "check.c"),"-o",str(exe)],check=True)
        subprocess.run([str(exe)],check=True)


if __name__ == "__main__":
    main()
