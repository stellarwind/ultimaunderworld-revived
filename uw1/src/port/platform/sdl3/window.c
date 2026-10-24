/* Desktop window placement belongs in the port's local settings, not the game saves.
   Run on SDL's main thread through PlatHooks.tick; Exhume's shared backend stays unchanged. */
#include <SDL3/SDL.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "plat.h"
#include "ui/settings.h"

int port_config_get(const char *, const char *, char *, size_t);
int port_config_set(const char *, const char *, const char *);

struct window_rect { int x, y, w, h; };
static struct {
    const char *home;
    SDL_Window *window;
    struct window_rect rect;
    int enabled, have_rect, initialized, restore_size, restore_pending;
    int maximized, restore_maximized;
    int scale, aspect, settings_was_open, fullscreen_was_on, dirty;
    Uint64 changed_at;
    void (*input_tick)(void);
} placement;

static int parse_rect(const char *text, struct window_rect *r)
{
    long v[4];
    int i;
    char *end;
    for (i = 0; i < 4; i++) {
        errno = 0;
        v[i] = strtol(text, &end, 10);
        if (errno || end == text || v[i] < -1000000 || v[i] > 1000000 ||
            (i < 3 ? *end != ',' : *end != 0)) return 0;
        text = end + (i < 3);
    }
    if (v[2] <= 0 || v[3] <= 0) return 0;
    r->x = (int)v[0]; r->y = (int)v[1]; r->w = (int)v[2]; r->h = (int)v[3];
    return 1;
}

/* Keep the client area and title bar inside a connected display's usable bounds.
   Negative coordinates on a display left/above the primary display are valid. */
static void fit_rect(SDL_Window *window, struct window_rect *r)
{
    SDL_DisplayID *displays;
    SDL_Rect bounds, best;
    long long best_area = -1;
    int count, i, have_bounds = 0, top = 40, left = 8, bottom = 8, right = 8;
    displays = SDL_GetDisplays(&count);
    if (!displays) return;
    for (i = 0; i < count; i++) {
        long long area;
        int x0, y0, x1, y1;
        if (!SDL_GetDisplayUsableBounds(displays[i], &bounds)) continue;
        x0 = r->x > bounds.x ? r->x : bounds.x;
        y0 = r->y > bounds.y ? r->y : bounds.y;
        x1 = r->x + r->w < bounds.x + bounds.w ? r->x + r->w : bounds.x + bounds.w;
        y1 = r->y + r->h < bounds.y + bounds.h ? r->y + r->h : bounds.y + bounds.h;
        area = x1 > x0 && y1 > y0 ? (long long)(x1 - x0) * (y1 - y0) : 0;
        if (!have_bounds || area > best_area) {
            best = bounds; best_area = area; have_bounds = 1;
        }
    }
    SDL_free(displays);
    if (!have_bounds) return;
    if (!SDL_GetWindowBordersSize(window, &top, &left, &bottom, &right) ||
        top < 0 || left < 0 || bottom < 0 || right < 0) { top = 40; left = bottom = right = 8; }
    bounds = best;
    bounds.x += left; bounds.y += top;
    bounds.w -= left + right; bounds.h -= top + bottom;
    if (bounds.w <= 0 || bounds.h <= 0) return;
    if (r->w < 320) r->w = 320;
    if (r->h < 200) r->h = 200;
    if (r->w > bounds.w) r->w = bounds.w;
    if (r->h > bounds.h) r->h = bounds.h;
    if (r->x < bounds.x) r->x = bounds.x;
    if (r->y < bounds.y) r->y = bounds.y;
    if (r->x + r->w > bounds.x + bounds.w) r->x = bounds.x + bounds.w - r->w;
    if (r->y + r->h > bounds.y + bounds.h) r->y = bounds.y + bounds.h - r->h;
}

static void restore_rect(void)
{
    fit_rect(placement.window, &placement.rect);
    SDL_SetWindowSize(placement.window, placement.rect.w, placement.rect.h);
    SDL_SetWindowPosition(placement.window, placement.rect.x, placement.rect.y);
    SDL_SyncWindow(placement.window);
    placement.restore_pending = 0;
}

void port_window_save(void)
{
    char text[100];
    if (!placement.enabled || !placement.have_rect || !placement.dirty) return;
    snprintf(text, sizeof text, "%d,%d,%d,%d", placement.rect.x, placement.rect.y,
             placement.rect.w, placement.rect.h);
    if (port_config_set(placement.home, "window-geometry", text) != 0)
        fprintf(stderr, "uw1port: cannot save window placement in %s\n", placement.home);
    if (port_config_set(placement.home, "window-maximized", placement.maximized ? "1" : "0") != 0)
        fprintf(stderr, "uw1port: cannot save maximized window state in %s\n", placement.home);
    placement.dirty = 0;
}

void port_window_init(const char *home, int enabled, int restore_size,
                      int scale, int aspect, void (*input_tick)(void))
{
    char text[100];
    memset(&placement, 0, sizeof placement);
    placement.home = home;
    placement.enabled = enabled;
    placement.restore_size = restore_size;
    placement.scale = scale;
    placement.aspect = aspect;
    placement.input_tick = input_tick;
    if (enabled && port_config_get(home, "window-geometry", text, sizeof text) == 0)
        placement.have_rect = parse_rect(text, &placement.rect);
    if (enabled && restore_size && port_config_get(home, "window-maximized", text, sizeof text) == 0)
        placement.maximized = placement.restore_maximized = !strcmp(text, "1");
}

void port_window_tick(void)
{
    SDL_WindowFlags flags;
    struct window_rect now;
    int open, maximize_after_restore;
    if (placement.input_tick) placement.input_tick();
    if (!placement.enabled) return;
    if (!placement.window) {
        SDL_Window **windows;
        int count;
        windows = SDL_GetWindows(&count);
        if (windows && count) placement.window = windows[0];
        SDL_free(windows);
        if (!placement.window) return;
    }
    flags = SDL_GetWindowFlags(placement.window);
    open = settings_open();
    if (flags & SDL_WINDOW_FULLSCREEN) {
        placement.fullscreen_was_on = 1;
        placement.settings_was_open = open;
        return;
    }
    /* Minimizing must retain the preceding maximized/windowed choice. */
    if (flags & SDL_WINDOW_MINIMIZED) return;
    if (flags & SDL_WINDOW_MAXIMIZED) {
        placement.fullscreen_was_on = 0;
        placement.restore_maximized = 0;
        if (!placement.maximized) {
            placement.maximized = 1;
            placement.dirty = 1;
            port_window_save();
        }
        return;
    }
    maximize_after_restore = placement.restore_maximized ||
                             (placement.fullscreen_was_on && placement.maximized);
    placement.restore_maximized = 0;
    if (placement.maximized && !maximize_after_restore) {
        placement.maximized = 0;
        placement.dirty = 1;
    }
    if (!SDL_GetWindowPosition(placement.window, &now.x, &now.y) ||
        !SDL_GetWindowSize(placement.window, &now.w, &now.h) || now.w <= 0 || now.h <= 0) return;
    if (!placement.initialized) {
        if (!placement.have_rect) placement.rect = now;
        else if (!placement.restore_size) { placement.rect.w = now.w; placement.rect.h = now.h; }
        placement.have_rect = placement.initialized = 1;
        placement.restore_pending = 1;
    }
    /* The settings screen temporarily doubles scale-1 windows. Its closing resize must
       not replace a manually resized game window, nor its remembered geometry. */
    if (placement.fullscreen_was_on || (placement.settings_was_open && !open && placement.scale < 2))
        placement.restore_pending = 1;
    placement.fullscreen_was_on = 0;
    if (placement.restore_pending) {
        restore_rect();
        if (!SDL_GetWindowPosition(placement.window, &now.x, &now.y) ||
            !SDL_GetWindowSize(placement.window, &now.w, &now.h)) return;
    }
    if (maximize_after_restore) {
        /* Restore the floating rectangle first so the Restore button returns to it. */
        placement.maximized = 1;
        placement.dirty = 1;
        SDL_MaximizeWindow(placement.window);
        SDL_SyncWindow(placement.window);
        port_window_save();
        return;
    }
    placement.settings_was_open = open;
    if (open && placement.scale < 2) { now.w = placement.rect.w; now.h = placement.rect.h; }
    /* Persist the initial rectangle too, but never rewrite an unchanged file every frame. */
    if (memcmp(&now, &placement.rect, sizeof now) != 0 || !placement.changed_at) {
        placement.rect = now;
        placement.dirty = 1;
        placement.changed_at = SDL_GetTicks() + 1;
    }
    if (placement.dirty && SDL_GetTicks() + 1 - placement.changed_at >= 300) port_window_save();
}

/* Display options go through this wrapper: fullscreen/integer scaling must preserve
   the floating rectangle. An explicit window scale/aspect change still resizes it. */
void port_window_display(int fullscreen, int scale, int aspect, int integer_scale)
{
    int resize = scale != placement.scale || aspect != placement.aspect;
    placement.scale = scale; placement.aspect = aspect;
    if (resize && placement.have_rect) {
        placement.rect.w = 320 * scale;
        placement.rect.h = (aspect ? 240 : 200) * scale;
    }
    plat_set_display(fullscreen, scale, aspect, integer_scale);
    if (placement.enabled && placement.have_rect) placement.restore_pending = 1;
}
