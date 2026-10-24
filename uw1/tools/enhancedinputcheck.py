"""Check the combined input option and migration through the actual registry/config code."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    if not cc:
        raise SystemExit("enhancedinputcheck: a C11 compiler is required")
    runtime = ROOT.parent / "exhume/runtime/port"
    config = (runtime / "sys/gamedir.c").read_text()
    code = '''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "portgame.h"
#include "sys/enhance.h"
#define MAXP 4096
'''
    code += config[config.index("static void cfg_path("):]
    for path in ("src/port/sys/enhance.c", "src/port/sys/enhtab.c"):
        code += '\n#include "' + (ROOT / path).as_posix() + '"\n'
    code += r'''
int main(int argc,char **argv) {
    assert(argc==2);
    enhance_init(enhance_table,ENH_COUNT,"UW1");
    const char *names[]={"modern-keys","single-action-toggle","enhanced-input"};
    for(unsigned i=0;i<3;i++) {
        uint32_t mask=0;
        assert(!enhance_parse(names[i],&mask,1,1));
        assert(mask==(1u<<ENH_ENHANCED_INPUT));
        assert(!enhance_parse(names[i],&mask,0,1) && mask==0);
    }
    int count=0;
    for(int i=0;i<enhance_count();i++) {
        const struct enhance_flag *flag=enhance_flag(i);
        count+=!strcmp(flag->name,"enhanced-input");
        assert(strcmp(flag->name,"modern-keys") && strcmp(flag->name,"single-action-toggle"));
    }
    assert(count==1);
    const char *old[]={"modern-keys","single-action-toggle","modern-keys,single-action-toggle"};
    for(unsigned i=0;i<3;i++) {
        char input[256],saved[512];uint32_t mask=0;
        snprintf(input,sizeof input,"skip-intro,%s,steady-swimming",old[i]);
        assert(!port_config_set(argv[1],"enhance",input));
        assert(!port_config_set(argv[1],"volume","200"));
        assert(!enhance_load(argv[1],&mask));
        assert(mask==((1u<<ENH_SKIP_INTRO)|(1u<<ENH_ENHANCED_INPUT)|(1u<<ENH_STEADY_SWIMMING)));
        assert(!port_config_get(argv[1],"enhance",saved,sizeof saved));
        assert(strstr(saved,"enhanced-input") && !strstr(saved,"modern-keys") && !strstr(saved,"single-action-toggle"));
        uint32_t reloaded=0;assert(!enhance_load(argv[1],&reloaded) && reloaded==mask);
        assert(!port_config_get(argv[1],"volume",saved,sizeof saved) && !strcmp(saved,"200"));
    }
    puts("enhancedinputcheck: one combined option, legacy aliases, migration, reload and other settings preserved");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="uw1-enhanced-input-") as work:
        work = Path(work)
        source = work / "check.c"
        source.write_text(code)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I",
                        str(ROOT / "src/port"), "-I", str(runtime), str(source),
                        "-o", str(exe)], check=True)
        subprocess.run([str(exe), str(work)], check=True)


if __name__ == "__main__":
    main()
