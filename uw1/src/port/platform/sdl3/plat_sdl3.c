/* Use the shared SDL backend with optional output gain above its normal volume.
   SDL applies the gain during sample conversion, avoiding signed 16-bit wraparound. */
#include <SDL3/SDL.h>
#include <stdatomic.h>
#include "port.h"
#include "sound/audio.h"

static _Atomic int output_gain = 100;

void port_audio_set_volume(int percent)
{
    if (percent < 0) percent = 0;
    if (percent > 200) percent = 200;
    audio_set_volume(percent > 100 ? 100 : percent);
    atomic_store(&output_gain, percent > 100 ? percent : 100);
}

static bool SDLCALL put_audio_with_gain(SDL_AudioStream *stream, const void *data, int len)
{
    SDL_SetAudioStreamGain(stream, (float)atomic_load(&output_gain) / 100.0f);
    return SDL_PutAudioStreamData(stream, data, len);
}

#define SDL_PutAudioStreamData put_audio_with_gain
#include "../../../../../exhume/runtime/port/platform/sdl3/plat_sdl3.c"
#undef SDL_PutAudioStreamData
