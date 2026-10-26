/* Called on the settings/UI thread, including when the game thread is stuck.
   Never wait for a game callback or inspect mutable game pointers on this thread.
   Windows' minidump captures every thread and memory even if the game cannot park. */
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#define mouse_event win32_mouse_event
#include <windows.h>
#undef mouse_event
#include <dbghelp.h>
#include <direct.h>
#else
#include <sys/stat.h>
#endif
#include "port.h"
#include "ui/settings.h"

extern const char *port_home;
extern const char *port_debug_dump_names[];
void port_debug_state_report(FILE *f);

#ifdef _WIN32
static int native_dump(const char *base, FILE *report)
{
    typedef BOOL (WINAPI *dump_fn)(HANDLE, DWORD, HANDLE, MINIDUMP_TYPE,
                                   PMINIDUMP_EXCEPTION_INFORMATION,
                                   PMINIDUMP_USER_STREAM_INFORMATION,
                                   PMINIDUMP_CALLBACK_INFORMATION);
    HMODULE lib = LoadLibraryA("dbghelp.dll");
    dump_fn dump = lib ? (dump_fn)(void *)GetProcAddress(lib, "MiniDumpWriteDump") : NULL;
    char path[4096], exe[4096];
    HANDLE file;
    int ok = 0;
    if (!dump) {
        fprintf(report, "MiniDumpWriteDump unavailable (Windows error %lu)\n", (unsigned long)GetLastError());
        if (lib) FreeLibrary(lib);
        return 0;
    }
    snprintf(path, sizeof path, "%s.dmp", base);
    file = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) {
        ok = dump(GetCurrentProcess(), GetCurrentProcessId(), file,
                  (MINIDUMP_TYPE)(MiniDumpWithFullMemory | MiniDumpWithHandleData | MiniDumpWithThreadInfo),
                  NULL, NULL, NULL) != 0;
        fprintf(report, "Memory/thread dump: %s (Windows error %lu)\n", ok ? "written" : "FAILED",
                ok ? 0ul : (unsigned long)GetLastError());
        CloseHandle(file);
        if (!ok) DeleteFileA(path);  /* an incomplete dump cannot be debugged */
    } else {
        fprintf(report, "Cannot create memory dump (Windows error %lu)\n", (unsigned long)GetLastError());
    }
    FreeLibrary(lib);
    /* Keep the exact executable (with its symbols) beside the dump: rebuilding later
       otherwise makes the thread addresses difficult or impossible to interpret. */
    snprintf(path, sizeof path, "%s.exe", base);
    {
        DWORD n = GetModuleFileNameA(NULL, exe, sizeof exe);
        if (!n || n >= sizeof exe || !CopyFileA(exe, path, TRUE)) {
            fprintf(report, "Executable copy FAILED (Windows error %lu); keep the running executable.\n",
                    (unsigned long)GetLastError());
            ok = 0;
        }
    }
    return ok;
}
#endif

void port_debug_dump(int unused)
{
    char dir[4096], base[4096], path[4096], stamp[32];
    struct tm *local;
    time_t now = time(NULL);
    static unsigned sequence;
    FILE *f;
    int n, ok, parked;
    (void)unused;
    port_debug_dump_names[0] = "Dump failed (see log)";
    if (!port_home || !settings_open()) return;
    n = snprintf(dir, sizeof dir, "%s/debug", port_home);
    if (n < 0 || n >= (int)sizeof dir - 100) return;
#ifdef _WIN32
    ok = _mkdir(dir);
#else
    ok = mkdir(dir, 0700);
#endif
    if (ok && errno != EEXIST) {
        fprintf(stderr, "uw1port: cannot create debug folder %s: %s\n", dir, strerror(errno));
        return;
    }
    local = localtime(&now);
    if (!local || !strftime(stamp, sizeof stamp, "%Y%m%d-%H%M%S", local)) strcpy(stamp, "unknown-time");
    /* Exclusive creation also handles another run in the same second without replacing evidence. */
    do {
        snprintf(base, sizeof base, "%s/state-%s-%u", dir, stamp, ++sequence);
        snprintf(path, sizeof path, "%s.txt", base);
        f = fopen(path, "wx");
    } while (!f && errno == EEXIST);
    if (!f) {
        fprintf(stderr, "uw1port: cannot create debug report %s: %s\n", path, strerror(errno));
        return;
    }
    parked = port_game_parked();
    fprintf(f, "UW1 debug state, format 1\nLocal time: %s\nBuild: %s %s\nGame thread parked: %d\n",
            stamp, __DATE__, __TIME__, parked);
    if (parked) port_debug_state_report(f);
    else fprintf(f, "Game thread did not park. Live game globals deliberately not read.\n"
                    "On Windows, inspect the .dmp thread stacks and memory for the freeze.\n");
#ifdef _WIN32
    ok = native_dump(base, f);
#else
    fprintf(f, "Native memory/thread capture is available on Windows only.\n");
    ok = parked;
#endif
    if (ferror(f)) ok = 0;
    if (fclose(f)) ok = 0;
    port_debug_dump_names[0] = ok ? "Saved in home/debug" : "Partial (see debug/log)";
    fprintf(stderr, "uw1port: debug state %s: %s\n", ok ? "written" : "PARTIAL", path);
}
