/* User sound preferences belong to the local port config, rather than a saved game. */
#include <string.h>
#include "port.h"

extern const char *port_home;

int port_sound_enabled(int music, int fallback)
{
    char value[16];
    if (port_home && !port_config_get(port_home, music ? "music-enabled" : "effects-enabled",
                                     value, sizeof value)) {
        if (!strcmp(value, "0")) return 0;
        if (!strcmp(value, "1")) return 1;
    }
    return fallback != 0;
}

void port_sound_remember(int music, int enabled)
{
    if (port_home)
        port_config_set(port_home, music ? "music-enabled" : "effects-enabled", enabled ? "1" : "0");
}
