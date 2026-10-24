"""Regression checks for the actual SDL window-placement module, without game data.
A small deterministic SDL stand-in covers display changes and fullscreen/settings transitions.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    cc = os.environ.get("CC") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        raise SystemExit("windowcheck: a C11 compiler is required")
    header = r"""
#ifndef MOCK_SDL_H
#define MOCK_SDL_H
#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>
typedef uint64_t Uint64;
typedef uint64_t SDL_WindowFlags;
typedef unsigned SDL_DisplayID;
typedef struct { int x,y,w,h; SDL_WindowFlags flags; } SDL_Window;
typedef struct { int x,y,w,h; } SDL_Rect;
#define SDL_WINDOW_FULLSCREEN 1u
#define SDL_WINDOW_MINIMIZED 2u
#define SDL_WINDOW_MAXIMIZED 4u
#define SDL_free free
SDL_DisplayID *SDL_GetDisplays(int *n);
bool SDL_GetDisplayUsableBounds(SDL_DisplayID d, SDL_Rect *r);
bool SDL_GetWindowBordersSize(SDL_Window *w, int *t, int *l, int *b, int *r);
bool SDL_SetWindowSize(SDL_Window *w, int x, int y);
bool SDL_SetWindowPosition(SDL_Window *w, int x, int y);
bool SDL_SyncWindow(SDL_Window *w);
bool SDL_MaximizeWindow(SDL_Window *w);
bool SDL_GetWindowPosition(SDL_Window *w, int *x, int *y);
bool SDL_GetWindowSize(SDL_Window *w, int *x, int *y);
SDL_WindowFlags SDL_GetWindowFlags(SDL_Window *w);
SDL_Window **SDL_GetWindows(int *n);
Uint64 SDL_GetTicks(void);
#endif
"""
    code = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <SDL3/SDL.h>
static SDL_Window window;
static Uint64 ticks;
static int shown, writes, script_ticks;
static char kept[100], kept_max[8];
SDL_DisplayID *SDL_GetDisplays(int *n) {
    SDL_DisplayID *d = malloc(2*sizeof *d); *n=2; d[0]=1; d[1]=2; return d;
}
bool SDL_GetDisplayUsableBounds(SDL_DisplayID d, SDL_Rect *r) {
    *r = d==1 ? (SDL_Rect){0,0,1920,1080} : (SDL_Rect){-1280,0,1280,1024}; return true;
}
bool SDL_GetWindowBordersSize(SDL_Window *w,int *t,int *l,int *b,int *r) {
    (void)w; *t=32; *l=*b=*r=8; return true;
}
bool SDL_SetWindowSize(SDL_Window *w,int x,int y) { w->w=x; w->h=y; return true; }
bool SDL_SetWindowPosition(SDL_Window *w,int x,int y) { w->x=x; w->y=y; return true; }
bool SDL_SyncWindow(SDL_Window *w) { (void)w; return true; }
bool SDL_MaximizeWindow(SDL_Window *w) { w->flags|=SDL_WINDOW_MAXIMIZED; return true; }
bool SDL_GetWindowPosition(SDL_Window *w,int *x,int *y) { *x=w->x; *y=w->y; return true; }
bool SDL_GetWindowSize(SDL_Window *w,int *x,int *y) { *x=w->w; *y=w->h; return true; }
SDL_WindowFlags SDL_GetWindowFlags(SDL_Window *w) { return w->flags; }
SDL_Window **SDL_GetWindows(int *n) {
    SDL_Window **w=malloc(sizeof *w); *n=1; w[0]=&window; return w;
}
Uint64 SDL_GetTicks(void) { return ticks; }
int settings_open(void) { return shown; }
int port_config_get(const char *home,const char *key,char *out,size_t n) {
    const char *value;
    (void)home;
    value=!strcmp(key,"window-maximized") ? kept_max : kept;
    if (!*value) return -1;
    snprintf(out,n,"%s",value); return 0;
}
int port_config_set(const char *home,const char *key,const char *value) {
    (void)home;
    if (!strcmp(key,"window-maximized")) snprintf(kept_max,sizeof kept_max,"%s",value);
    else { assert(!strcmp(key,"window-geometry")); snprintf(kept,sizeof kept,"%s",value); }
    writes++; return 0;
}
void plat_set_display(int full,int scale,int aspect,int integer) {
    (void)integer; window.flags=full ? SDL_WINDOW_FULLSCREEN : 0;
    window.w=full ? 1920 : 320*scale; window.h=full ? 1080 : (aspect?240:200)*scale;
}
static void script_tick(void) { script_ticks++; }
"""
    code += '\n#include "' + (ROOT / "src/port/platform/sdl3/window.c").as_posix() + '"\n'
    code += r"""
static void setup(const char *saved,int enabled,int restore_size,int scale) {
    snprintf(kept,sizeof kept,"%s",saved);
    window=(SDL_Window){100,100,320*scale,240*scale,0};
    *kept_max=0;
    shown=writes=script_ticks=0; ticks=100;
    port_window_init("local",enabled,restore_size,scale,1,script_tick);
}
static void step(void) { ticks+=100; port_window_tick(); }
static void saved_is(const char *s) { port_window_save(); assert(!strcmp(kept,s)); }
int main(void) {
    struct window_rect r;
    int i;
    const char *bad[]={"", "x,2,3,4", "1,2,0,4", "1,2,-3,4", "1,2,3,4junk",
                       "1,2,3", "1,2,3,4,5", "999999999999999999999999,2,3,4"};
    for(i=0;i<(int)(sizeof bad/sizeof *bad);i++) assert(!parse_rect(bad[i],&r));
    assert(parse_rect("-1200,100,800,600",&r));
    setup("100,100,800,600",1,1,3); step();
    assert(window.x==100 && window.y==100 && window.w==800 && window.h==600);
    saved_is("100,100,800,600");
    i=writes; for(int j=0;j<20;j++) step(); assert(writes==i);
    window.x=250; window.y=200; window.w=900; window.h=650; step();
    assert(writes==i); for(int j=0;j<4;j++) step();
    assert(writes==i+2); saved_is("250,200,900,650");
    /* Restart round-trip restores the exact last normal rectangle. */
    port_window_init("local",1,1,3,1,NULL); window=(SDL_Window){0,0,960,720,0}; step();
    assert(window.x==250 && window.y==200 && window.w==900 && window.h==650);
    window.flags=SDL_WINDOW_MAXIMIZED; window.x=0; window.y=0; window.w=1920; window.h=1080;
    step(); saved_is("250,200,900,650");
    window.flags=SDL_WINDOW_MINIMIZED; window.x=-32000; window.y=-32000;
    step(); saved_is("250,200,900,650");
    window.flags=0; port_window_display(1,3,1,1); step(); saved_is("250,200,900,650");
    port_window_display(0,3,1,1); step();
    assert(window.x==250 && window.y==200 && window.w==900 && window.h==650);
    /* Toggling integer scaling preserves custom size. Explicit scale/aspect changes win. */
    port_window_display(0,3,1,0); step(); assert(window.w==900 && window.h==650);
    port_window_display(0,2,1,0); step(); assert(window.w==640 && window.h==480);
    port_window_display(0,2,0,0); step(); assert(window.w==640 && window.h==400);
    setup("100,100,800,600",1,1,1); step();
    shown=1; window.w=640; window.h=480; step(); saved_is("100,100,800,600");
    shown=0; window.w=320; window.h=240; step();
    assert(window.w==800 && window.h==600);
    setup("50000,50000,800,600",1,1,3); step();
    assert(window.x>=8 && window.x+window.w<=1912 && window.y>=32 && window.y+window.h<=1072);
    setup("-1200,100,800,600",1,1,3); step(); assert(window.x==-1200 && window.y==100);
    setup("100,100,999999,999999",1,1,3); step(); assert(window.w<=1904 && window.h<=1040);
    setup("100,100,800,600",1,0,2); step(); assert(window.w==640 && window.h==480);
    setup("1,2,0,4",1,1,3); step(); assert(window.w==960 && window.h==720);
    setup("100,100,800,600",0,1,3); step(); port_window_save();
    assert(writes==0 && window.w==960 && script_ticks==1);
    setup("100,100,800,600",1,1,3); window.flags=SDL_WINDOW_FULLSCREEN; step();
    assert(writes==0); port_window_display(0,3,1,1); step();
    assert(window.w==800 && window.h==600 && window.x==100 && window.y==100);
    /* Persist maximize/unmaximize across restarts without losing the floating size. */
    setup("250,200,900,650",1,1,3); step();
    window.flags=SDL_WINDOW_MAXIMIZED; step(); assert(!strcmp(kept_max,"1"));
    window.flags=SDL_WINDOW_MINIMIZED|SDL_WINDOW_MAXIMIZED; step();
    assert(!strcmp(kept_max,"1"));
    port_window_init("local",1,1,3,1,NULL); window=(SDL_Window){0,0,960,720,0}; step();
    assert(window.flags & SDL_WINDOW_MAXIMIZED);
    assert(placement.rect.x==250 && placement.rect.y==200 && placement.rect.w==900 && placement.rect.h==650);
    window.flags=0; window.x=250; window.y=200; window.w=900; window.h=650; step(); port_window_save();
    assert(!strcmp(kept_max,"0"));
    port_window_init("local",1,1,3,1,NULL); window=(SDL_Window){0,0,960,720,0}; step();
    assert(!(window.flags & SDL_WINDOW_MAXIMIZED) && window.w==900 && window.h==650);
    window.flags=SDL_WINDOW_MAXIMIZED; step();
    port_window_display(1,3,1,1); step();
    assert(placement.maximized);
    port_window_display(0,3,1,1); step();
    assert(window.flags & SDL_WINDOW_MAXIMIZED);
    assert(!strcmp(kept_max,"1"));
    step(); /* Observe the completed fullscreen-to-maximized transition. */
    window.flags=0; step(); assert(!(window.flags & SDL_WINDOW_MAXIMIZED));
    port_window_save(); assert(!strcmp(kept_max,"0"));
    puts("windowcheck: placement round-trip, debounced writes, fullscreen/maximized/minimized, settings, display changes, invalid config, CLI scale and test isolation passed");
    return 0;
}
"""
    with tempfile.TemporaryDirectory(prefix="uw1-window-") as work:
        work = Path(work)
        (work / "SDL3").mkdir()
        (work / "SDL3/SDL.h").write_text(header)
        (work / "check.c").write_text(code)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        rt = ROOT.parent / "exhume/runtime/port"
        subprocess.run([cc,"-std=gnu11","-Wall","-Wextra","-Werror","-I",str(work),
                        "-I",str(ROOT / "src/port"),"-I",str(rt / "platform"),"-I",str(rt),str(work / "check.c"),"-o",str(exe)],check=True)
        subprocess.run([str(exe)],check=True)


if __name__ == "__main__":
    main()
