"""Check local sound-toggle persistence and real SDL output gain without a device."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile

from weaponswaycheck import function

ROOT = Path(__file__).resolve().parents[1]


def main():
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    if not cc:
        raise SystemExit("audiocheck: a C11 compiler and SDL3 development files are required")
    runtime = ROOT.parent / "exhume/runtime/port"
    config = (runtime / "sys/gamedir.c").read_text()
    config = config[config.index("static void cfg_path("):]
    gain = (ROOT / "src/port/platform/sdl3/plat_sdl3.c").read_text()
    gain = gain.split("#define SDL_PutAudioStreamData")[0]
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "portgame.h"
#define MAXP 4096
const char *port_home;
static int base_volume;
void audio_set_volume(int value) { base_volume=value; }
'''
    code += config + '\n' + gain + '\n'
    code += '#include "' + (ROOT / "src/port/sys/sound_settings.c").as_posix() + '"\n'
    code += r'''
#define far
static int options_quick, music, effects;
static void turn_music(char on) { music=on; }
static void turn_fx(char on) { effects=on; }
static void draw_music_and_sound_page(void) {}
static void close_option_panel(void) {}
static void set_options_page(int page) { (void)page; }
'''
    options = (ROOT / "src/ui/OPTIONS.C").read_text()
    code += function(options, "choose_music") + '\n' + function(options, "choose_sounds")
    code += r'''
int main(int argc,char **argv) {
    assert(argc==3);port_home=argv[1];
    if(!strcmp(argv[2],"write")) {
        assert(port_sound_enabled(1,1)==1 && port_sound_enabled(0,0)==0);
        assert(!port_config_set(port_home,"volume","200"));
        choose_music(3);choose_sounds(3);
        assert(!music && !effects);
        return 0;
    }
    /* A fresh process must override conflicting saved-game values. */
    assert(port_sound_enabled(1,1)==0 && port_sound_enabled(0,1)==0);
    choose_music(2);choose_sounds(2);
    assert(port_sound_enabled(1,1)==0 && port_sound_enabled(0,1)==0);
    choose_music(4);choose_sounds(4);
    assert(music && effects && port_sound_enabled(1,0)==1 && port_sound_enabled(0,0)==1);
    char value[16];assert(!port_config_get(port_home,"volume",value,sizeof value));
    assert(!strcmp(value,"200"));
    assert(!port_config_set(port_home,"music-enabled","invalid"));
    assert(port_sound_enabled(1,0)==0 && port_sound_enabled(1,1)==1);
    int levels[]={-10,0,50,100,120,150,200,250};
    for(unsigned n=0;n<sizeof levels/sizeof levels[0];n++) {
        int level=levels[n]<0 ? 0 : levels[n]>200 ? 200 : levels[n];
        port_audio_set_volume(levels[n]);
        assert(base_volume==(level>100 ? 100 : level));
        SDL_AudioSpec spec={.format=SDL_AUDIO_S16,.channels=1,.freq=44100};
        SDL_AudioStream *stream=SDL_CreateAudioStream(&spec,&spec);assert(stream);
        int16_t input[]={10000,-10000,30000,-30000},output[4];
        for(int i=0;i<4;i++) input[i]=input[i]*base_volume/100;
        assert(put_audio_with_gain(stream,input,sizeof input));
        assert(SDL_FlushAudioStream(stream));
        assert(SDL_GetAudioStreamData(stream,output,sizeof output)==sizeof output);
        int raw[]={10000,-10000,30000,-30000};
        for(int i=0;i<4;i++) {
            int expected=raw[i]*level/100;
            if(expected>32767) expected=32767;
            if(expected< -32768) expected= -32768;
            assert(abs((int)output[i]-expected)<=1);
        }
        SDL_DestroyAudioStream(stream);
    }
    puts("audiocheck: on/off persistence across processes, saved-game overrides, config preservation and SDL gain/clipping passed");
    return 0;
}
'''
    flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "sdl3"], text=True))
    flags = [flag for flag in flags if flag != "-mwindows"]
    with tempfile.TemporaryDirectory(prefix="uw1-audio-") as work:
        work = Path(work)
        source = work / "check.c"
        source.write_text(code)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I",
                        str(ROOT / "src/port"), "-I", str(runtime), str(source),
                        "-o", str(exe), *flags], check=True)
        for mode in ("write", "read"):
            subprocess.run([str(exe), str(work), mode], check=True)


if __name__ == "__main__":
    main()
