"""Exercise the real F11 dump row and Windows memory capture, without game assets.
Run with Python and a MinGW C compiler (CC, or gcc on PATH).
"""
from pathlib import Path
import hashlib
import os
import re
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT.parent / "exhume/runtime/port"


def main():
    if os.name != "nt":
        raise SystemExit("debugdumpcheck: Windows native capture check requires Windows")
    cc = os.environ.get("CC") or shutil.which("gcc")
    if not cc:
        raise SystemExit("debugdumpcheck: a MinGW C compiler is required")
    table = (ROOT / "src/port/sys/settab.c").read_text()
    row = re.search(r"\[R_DUMP\]\s*=\s*(\{.*?\}),", table, re.S).group(1)
    names = re.search(r'const char \*port_debug_dump_names\[\].*?;', table).group(0)
    harness = r'''
#define mouse_event win32_mouse_event
#include <windows.h>
#undef mouse_event
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ui/settings.h"
#include "sys/enhance.h"
const char *port_home;
static int parked, reports;
int port_game_parked(void) { return parked; }
void port_debug_state_report(FILE *f) { reports++; fputs("TEST parked state\n", f); }
int port_config_get(const char *h, const char *k, char *v, size_t n) { return -1; }
int port_config_set(const char *h, const char *k, const char *v) { assert(0); return -1; }
int enhance_count(void) { return 0; }
const struct enhance_flag *enhance_flag(int i) { return NULL; }
int enhance_load(const char *h, uint32_t *v) { *v=0; return 0; }
int enhance_save(const char *h, uint32_t v) { assert(0); return -1; }
void port_debug_dump(int unused);
'''
    harness += names + "\nstatic const struct setting table[] = {" + row + "};\n"
    harness += r'''
/* Simulate a game thread that cannot reach a cooperative pause point. */
static DWORD WINAPI stuck(void *p) { for (;;) Sleep(1); return 0; }
int main(int argc, char **argv) {
    HANDLE thread = CreateThread(NULL, 0, stuck, NULL, 0, NULL);
    assert(thread && argc == 2);
    port_home = argv[1];
    settings_init(port_home, table, 1, "Test");
    settings_show(1);
    for (int i=0; i<4; i++) settings_key(SET_KEY_TAB);
    settings_key(SET_KEY_ENTER);
    assert(!strcmp(port_debug_dump_names[0], "Saved in home/debug"));
    assert(reports == 0);
    parked = 1;
    settings_key(SET_KEY_ENTER); /* repeated activation must create another dump */
    assert(reports == 1);
    assert(!strcmp(port_debug_dump_names[0], "Saved in home/debug"));
    settings_pointer(30, 80, 1); /* the mouse uses the same action */
    settings_pointer(30, 80, 0);
    assert(reports == 2);
    port_home = "Z:/nonexistent-debugdumpcheck/path";
    settings_key(SET_KEY_ENTER);
    assert(!strcmp(port_debug_dump_names[0], "Dump failed (see log)"));
    settings_show(0);
    CloseHandle(thread);
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="uw1-debugdump-") as tmp:
        work = Path(tmp)
        (work / "port.h").write_text("int port_game_parked(void);\n")
        (work / "test.c").write_text(harness)
        exe = work / "check.exe"
        subprocess.run([cc, "-std=c11", "-I", str(work), "-I", str(RUNTIME),
                        str(work / "test.c"), str(ROOT / "src/port/sys/debugdump.c"),
                        str(RUNTIME / "ui/settings.c"), str(RUNTIME / "ui/font.c"),
                        "-o", str(exe)], check=True)
        subprocess.run([str(exe), str(work)], check=True, timeout=45)
        reports = sorted((work / "debug").glob("*.txt"))
        assert len(reports) == 3, reports
        assert "did not park" in reports[0].read_text()
        assert "TEST parked state" in reports[1].read_text()
        for report in reports:
            dump = report.with_suffix(".dmp").read_bytes()
            signature, _, count, directory = struct.unpack_from("<4I", dump)
            assert signature == 0x504D444D  # MDMP
            streams = {struct.unpack_from("<3I", dump, directory + i*12)[0]:
                       struct.unpack_from("<3I", dump, directory + i*12)[2] for i in range(count)}
            assert 9 in streams  # Memory64ListStream: full process memory
            assert struct.unpack_from("<I", dump, streams[3])[0] >= 2  # ThreadListStream
            assert hashlib.sha256(report.with_suffix(".exe").read_bytes()).digest() == hashlib.sha256(exe.read_bytes()).digest()
        print("debugdumpcheck: Enter, repeat, mouse, stuck/parked thread, native stacks/memory, exact executable and write failure passed")


if __name__ == "__main__":
    main()
