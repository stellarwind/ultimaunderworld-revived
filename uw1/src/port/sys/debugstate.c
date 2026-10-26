/* Only called while the game is parked at a clock read and settings remain open.
   In a hard freeze debugdump.c uses the native dump instead of racing these globals. */
#include <stdio.h>
#include "compat.h"
#include "motion.h"
#include "player.h"
#include "sys.h"
#include "sys/enhance.h"

void port_debug_state_report(FILE *f)
{
    int x, y;
    fprintf(f, "Level=%d tile=%d facing=%u heading=%u input=%d fiz_update=%u enhancements=%08lx\n",
            PlayerLevel, GrSq, (unsigned)(uint16)PlayerFacing, (unsigned)(uint16)PlayerHeading,
            PlayerInput, (unsigned)fiz_update, (unsigned long)enhance_on);
    fprintf(f, "PN: xyz=%d,%d,%d speed=%d heading=%u time=%d terrain=%02x flags=%02x impact=%u\n"
               "    velocity=%d,%d,%d acceleration=%d,%d,%d radius=%u height=%u\n",
            PN.x, PN.y, PN.z, PN.speed, (unsigned)(uint16)PN.heading, PN.time, PN.terrain, PN.flags,
            PN.impact, PN.vel[0], PN.vel[1], PN.vel[2], PN.acc[0], PN.acc[1], PN.acc[2], PN.radius, PN.height);
    fprintf(f, "MP: steps=%d done=%d rem=%d dt=%d major=%d minor=%d hit=%d targz=%d zspeed=%d\n",
            MP.steps, MP.done, MP.rem, MP.dt, MP.major, MP.minor, MP.hit, MP.targz, MP.zspeed);
    fprintf(f, "Ppd: xyz=%d,%d,%d index=%d hits=%04x,%04x floor=%u top=%u slope=%u open=%u found=%u first=%d count=%u\n",
            Ppd.x, Ppd.y, Ppd.z, Ppd.index, (unsigned)(uint16)Ppd.hits0, (unsigned)(uint16)Ppd.hits1,
            Ppd.floor, Ppd.top, Ppd.slope, Ppd.open, Ppd.found, Ppd.first, Ppd.count);
    if (!mapdata || PlayerLevel < 1 || PlayerLevel > NUM_LEVELS) return;
    for (y = (PN.y >> 8) - 2; y <= (PN.y >> 8) + 2; y++) {
        for (x = (PN.x >> 8) - 2; x <= (PN.x >> 8) + 2; x++) {
            const struct Tile *t;
            if (x < 0 || x >= MAP_SIZE || y < 0 || y >= MAP_SIZE) continue;
            t = &mapdata[y * MAP_SIZE + x];
            fprintf(f, "tile %d,%d: type=%u height=%u floor=%u objects=%u wall=%u\n",
                    x, y, t->type, t->height, t->floor, t->objects.f.index, TILE_WALL(t));
        }
    }
}
