/* smooth-weapon-sway: a cosmetic, clock-driven replacement for the random per-frame
   draw offset. PANELS.C still calls jiggle_weapon, preserving the game's RNG and state. */
#include <stdint.h>

static uint32_t last_tick;
static unsigned phase;
static int moving;

/* One quarter of a sine in Q8, interpolated across the 64 samples of a full turn. */
static int sine_sample(unsigned index)
{
    static const int quarter[17] = {
        0, 25, 50, 74, 98, 121, 142, 162, 181, 198, 213, 226, 237, 245, 251, 255, 256
    };
    int sign;
    index &= 63;
    sign = index >= 32 ? -1 : 1;
    index &= 31;
    if (index > 16) index = 32 - index;
    return sign * quarter[index];
}

int port_weapon_sway(int how, int swinging, unsigned ticks)
{
    uint32_t elapsed = (uint32_t)ticks - last_tick;
    unsigned fraction, index;
    int amplitude, value;
    last_tick = ticks;
    if (!how || swinging) {
        moving = 0;
        phase = 0;
        return 0;
    }
    if (!moving || elapsed > 256) {
        moving = 1;
        phase = 0;
    } else {
        /* The game clock is 256 Hz: walking is 1.5 cycles/s, running 2 cycles/s.
           Unsigned subtraction also handles the clock wrapping. */
        phase = (phase + elapsed * (how >= 2 ? 512u : 384u)) & 0xFFFFu;
    }
    amplitude = how >= 2 ? 9 : 4;
    index = phase >> 10;
    fraction = phase & 1023u;
    value = (sine_sample(index) * (int)(1024u - fraction) +
             sine_sample(index + 1) * (int)fraction) / 1024;
    return value * amplitude / 256;
}
