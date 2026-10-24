/* Single Action Toggle's host cancellation. SDL dispatches event watches before the
   platform translates focus loss into releases, so those releases never activate actions. */
#include <SDL3/SDL.h>
#include "portgame.h"
#include "sys/enhance.h"

static bool cancel_action(void *unused, SDL_Event *event)
{
    (void)unused;
    if (event->type == SDL_EVENT_WINDOW_FOCUS_LOST ||
        event->type == SDL_EVENT_QUIT ||
        (event->type == SDL_EVENT_KEY_DOWN && !event->key.repeat &&
         (event->key.scancode == SDL_SCANCODE_F11
#ifdef __APPLE__
          || (event->key.scancode == SDL_SCANCODE_COMMA && (event->key.mod & SDL_KMOD_GUI))
#endif
         )))
        port_single_action_cancel();
    return true;
}

void port_single_action_init(void)
{
    if (ENHANCED(ENH_ENHANCED_INPUT)) SDL_AddEventWatch(cancel_action, NULL);
}
