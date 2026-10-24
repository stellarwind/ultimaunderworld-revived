/* One visible Enhanced Input option, with aliases for the two settings it replaces.
   Keep the shared registry, including command-line and replay parsing. */
#include <string.h>
#include "sys/enhance.h"

static const char *input_name(const char *name)
{
    return !strcmp(name, "modern-keys") || !strcmp(name, "single-action-toggle")
        ? "enhanced-input" : name;
}

static int enhancement_name_compare(const char *a, const char *b)
{
    return strcmp(input_name(a), input_name(b));
}

#define strcmp enhancement_name_compare
#define enhance_load original_enhance_load
#include "../../../../exhume/runtime/port/sys/enhance.c"
#undef enhance_load
#undef strcmp

int enhance_load(const char *home, uint32_t *mask)
{
    char names[512];
    int result = original_enhance_load(home, mask);
    if (!result && !port_config_get(home, "enhance", names, sizeof names)
        && (strstr(names, "modern-keys") || strstr(names, "single-action-toggle")))
        enhance_save(home, *mask);
    return result;
}
