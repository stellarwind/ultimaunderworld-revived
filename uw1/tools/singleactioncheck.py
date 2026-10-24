"""Exercise the actual port keyboard queue and game input reader, without game assets.
Run with python tools/singleactioncheck.py (a C11 compiler is required).
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT.parent / "exhume/runtime/port"


def function(source, name):
    start = source.index("int far " + name + "(")
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    cc = os.environ.get("CC") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        raise SystemExit("singleactioncheck: a C11 compiler is required")
    mouse = (ROOT / "src/ui/MOUSE.C").read_text()
    header = r"""
#ifndef TEST_PORT_H
#define TEST_PORT_H
#include <stdint.h>
#include "portgame.h"
extern unsigned char seg063[0xAB0];
static inline void port_setw(unsigned char *p, uint16_t v) { p[0] = v; p[1] = v >> 8; }
#endif
"""
    harness = r"""
#include <assert.h>
#include <ctype.h>
#include <stdio.h>
#include "port.h"
#include "sys/enhance.h"
unsigned char seg063[0xAB0];
uint32_t enhance_on;
#define far
#define KEY_SHIFT 0x400
#define KEY_ALT 0x200
#define KEY_CTRL 0x100
#define KEY() key()
static uint32_t now;
#define GAME_TIME() now
static uint32_t key_time;
static int key_index;
static unsigned char *key_on = seg063 + 0x1EB, *Asc = seg063 + 0x10;
static unsigned char *Shift = seg063 + 0x1E2, *Alt = seg063 + 0x1E3;
static unsigned char *Ctrl = seg063 + 0x1E4, *CapsLock = seg063 + 0x1E8;
"""
    harness += '\n#include "' + (ROOT / "src/port/sys/keyqueue.c").as_posix() + '"\n'
    harness += function(mouse, "do_keyarray_input") + "\n"
    harness += function(mouse, "do_keyboard_input") + "\n"
    harness += r"""
static int read_input(int array) { now += 100; return do_keyboard_input((char)array); }
static void reset(int enhanced, int look) {
    int i;
    memset(seg063, 0, sizeof seg063);
    memset(toggle_pending, 0, sizeof toggle_pending);
    toggle_released = -1;
    held = held_e0 = last_e0 = 0; held_ms = 0;
    atomic_store(&write_ptr, 0x300); SETW(0x26C, 0x300);
    SETW(0x1E0, 1);  /* Accept repeats, as the game's held-key path does. */
    SETW(0x1E9, 2);
    for (i = 0; i < 6; ++i) {
        SETW(0x29B + i * 16, i == 0 ? 0x2A : i == 1 ? 0x38 : i == 2 ? 0x1D : 0x7E);
        SETW(0x2A3 + i * 16, i == 0 ? 0x36 : i == 1 ? 0x38 : i == 2 ? 0x1D : 0x7E);
    }
    for (i = 0x3B; i <= 0x44; ++i) Asc[i] = Asc[i + 128] = (unsigned char)(0x80 + i - 0x3B);
    Asc[0x11] = 'w'; Asc[0x11 + 128] = 'W';
    Asc[0x0F] = 9; Asc[0x0F + 128] = 0xA3;
    Asc[0x29] = '`'; Asc[0x29 + 128] = '~';
    enhance_on = (enhanced ? 1u << ENH_SINGLE_ACTION_TOGGLE : 0) | (look ? 1u << ENH_MOUSE_LOOK : 0);
    now = 1000; key_time = 0; key_index = 0;
    seg019_598();
}
int main(void) {
    int scan, i, array;
    for (array = 0; array <= 1; ++array) {
        for (scan = 0x3B; scan <= 0x44; ++scan) {
            reset(1, 1);
            kbd_byte((uint8_t)scan);
            for (i = 0; i < 40; ++i) { kbd_tick_ms(100); assert(read_input(array) == -1); }
            kbd_byte((uint8_t)(scan | 0x80));
            assert(read_input(array) == 0x80 + scan - 0x3B);
            assert(read_input(array) == -1);
            kbd_byte((uint8_t)(scan | 0x80));  /* Duplicate releases do nothing. */
            assert(read_input(array) == -1);
            for (i = 0; i < 3; ++i) {
                kbd_byte((uint8_t)scan); kbd_byte((uint8_t)(scan | 0x80));
                assert(read_input(array) == 0x80 + scan - 0x3B);
            }
        }
        reset(1, 1);
        kbd_byte(0x29);
        for (i = 0; i < 40; ++i) { kbd_tick_ms(100); assert(read_input(array) == -1); }
        kbd_byte(0xA9); assert(read_input(array) == '`'); assert(read_input(array) == -1);
        reset(1, 1);
        /* Quick overlapping taps are delivered individually in release order. */
        kbd_byte(0x3B); kbd_byte(0x3F); kbd_byte(0xBF); kbd_byte(0xBB);
        assert(read_input(array) == 0x84); assert(read_input(array) == 0x80);
        assert(read_input(array) == -1);
        reset(1, 1);
        kbd_byte(0x2A); assert(read_input(array) == -1);
        kbd_byte(0x3F); assert(read_input(array) == -1);
        kbd_byte(0xAA); kbd_byte(0xBF);
        assert(read_input(array) == (0x84 | KEY_SHIFT));
        reset(1, 1);
        kbd_byte(0x1D); assert(read_input(array) == -1);
        kbd_byte(0x3F); assert(read_input(array) == -1);
        kbd_byte(0x9D); kbd_byte(0xBF);
        assert(read_input(array) == (0x84 | KEY_CTRL));
        reset(1, 1);
        kbd_byte(0x2A); assert(read_input(array) == -1);
        kbd_byte(0x29); assert(read_input(array) == -1);
        kbd_byte(0xA9); assert(read_input(array) == '`'); /* Physical tilde works too. */
        reset(1, 1);
        kbd_byte(0x3F); assert(read_input(array) == -1);
        port_single_action_cancel(); kbd_byte(0xBF);
        assert(read_input(array) == -1);
        /* Cancellation still works if press and synthetic release were not yet consumed. */
        kbd_byte(0x3F); port_single_action_cancel(); kbd_byte(0xBF);
        assert(read_input(array) == -1);
        kbd_byte(0x3F); kbd_byte(0xBF); assert(read_input(array) == 0x84);
        reset(1, 1);
        kbd_byte(0x3F); kbd_byte(0x11);
        assert(read_input(array) == 'w');
        kbd_byte(0xBF); assert(read_input(array) == 0x84);
        kbd_tick_ms(600); assert(read_input(array) == 'w');
        reset(0, 1);
        kbd_byte(0x3F); assert(read_input(array) == 0x84);
        kbd_tick_ms(600); assert(read_input(array) == 0x84);
        kbd_byte(0xBF); assert(read_input(array) == -1);
        reset(1, 1);
        enhance_on |= 1u << ENH_MODERN_KEYS;
        kbd_byte(0x0F);
        for (i = 0; i < 40; ++i) { kbd_tick_ms(100); assert(read_input(array) == -1); }
        kbd_byte(0x8F); assert(read_input(array) == 9); assert(read_input(array) == -1);
        kbd_byte(0x0F); port_single_action_cancel(); kbd_byte(0x8F);
        assert(read_input(array) == -1);
        kbd_byte(0x36); assert(read_input(array) == -1);
        kbd_byte(0x0F); assert(read_input(array) == -1);
        kbd_byte(0xB6); kbd_byte(0x8F);
        assert(read_input(array) == (0xA3 | KEY_SHIFT));
        reset(1, 1); /* Without modern-keys Tab stays an ordinary repeating key. */
        kbd_byte(0x0F); assert(read_input(array) == 9);
        kbd_tick_ms(600); assert(read_input(array) == 9);
        reset(0, 1);
        enhance_on |= 1u << ENH_MODERN_KEYS;
        kbd_byte(0x0F); assert(read_input(array) == 9);
        kbd_tick_ms(600); assert(read_input(array) == 9);
        reset(1, 0);  /* Grave remains a normal text key without mouse-look. */
        kbd_byte(0x29); assert(read_input(array) == '`');
        kbd_tick_ms(600); assert(read_input(array) == '`');
    }
    puts("singleactioncheck: both input paths passed: F1-F10, Tab/Shift+Tab, grave/tilde, long holds, taps, overlap, modifiers, cancellation, movement/text repeat and enhancement off");
    return 0;
}
"""
    with tempfile.TemporaryDirectory(prefix="uw1-single-action-") as work:
        work = Path(work)
        (work / "port.h").write_text(header)
        (work / "check.c").write_text(harness)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(work),
                        "-I", str(ROOT / "src/port"), "-I", str(RUNTIME),
                        str(work / "check.c"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)



def host_check():
    """Check the actual SDL watch, including registration before SDL startup."""
    if not shutil.which("pkg-config"):
        print("singleactioncheck: SDL event-watch check skipped (pkg-config unavailable)")
        return
    flags = subprocess.run(["pkg-config", "--cflags", "--libs", "sdl3"],
                           capture_output=True, text=True, check=True).stdout.split()
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    harness = r"""
#include <assert.h>
#include <stdio.h>
#include "portgame.h"
#include "sys/enhance.h"
uint32_t enhance_on = 1u << ENH_SINGLE_ACTION_TOGGLE;
static int cancelled;
void port_single_action_cancel(void) { ++cancelled; }
"""
    harness += '\n#include "' + (ROOT / "src/port/platform/sdl3/single_action.c").as_posix() + '"\n'
    harness += r"""
int main(void) {
    SDL_Event event;
    port_single_action_init();
    assert(SDL_Init(SDL_INIT_EVENTS));
    SDL_zero(event); event.type = SDL_EVENT_KEY_DOWN;
    event.key.scancode = SDL_SCANCODE_F5;
    assert(SDL_PushEvent(&event)); assert(cancelled == 0);
    event.key.scancode = SDL_SCANCODE_F11;
    assert(SDL_PushEvent(&event)); assert(cancelled == 1);
    event.key.repeat = true;
    assert(SDL_PushEvent(&event)); assert(cancelled == 1);
    SDL_zero(event); event.type = SDL_EVENT_WINDOW_FOCUS_LOST;
    assert(SDL_PushEvent(&event)); assert(cancelled == 2);
    SDL_zero(event); event.type = SDL_EVENT_WINDOW_FOCUS_GAINED;
    assert(SDL_PushEvent(&event)); assert(cancelled == 2);
    SDL_RemoveEventWatch(cancel_action, NULL);
    SDL_Quit();
    puts("singleactioncheck: SDL watch cancels on F11 and focus loss; repeats and ordinary keys leave pending actions alone");
    return 0;
}
"""
    with tempfile.TemporaryDirectory(prefix="uw1-single-action-sdl-") as work:
        work = Path(work)
        (work / "check.c").write_text(harness)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "src/port"), "-I", str(RUNTIME),
                        str(work / "check.c"), "-o", str(exe), *flags], check=True)
        subprocess.run([str(exe)], check=True)
    print("singleactioncheck: SDL focus-loss and settings cancellation checks passed")


if __name__ == "__main__":
    main()
    host_check()
