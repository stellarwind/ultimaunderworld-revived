"""Check the renderer's divide recovery against its instruction-for-instruction handler.
No game assets required. Uses the actual machine runtime and UW1 fault dispatcher.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT.parent / "exhume/runtime/port"


def main():
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    if not cc:
        raise SystemExit("divfaultcheck: a C11 compiler is required")
    source = (ROOT / "src/port/3d/tmapops.c").read_text()
    # Execute the unmodified translated handler as the reference, including its IRET.
    handler = source[source.index("L692C: /* L692C */"):]
    handler = handler[:handler.index("return ASM_IRET;") + len("return ASM_IRET;")]
    code = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include "x86/asmrt.h"
unsigned char port_code_block[CODE_PARAS * 16u + 0x10000];
unsigned char seg063[SEG063_SIZE];
uint8_t *asm_vga_base;
static unsigned char stack[0x10002];
static jmp_buf halted;
uint8_t vga_read(uint16_t off) { abort(); }
void vga_write(uint16_t off, uint8_t value) { abort(); }
void port_halt(const char *why) { longjmp(halted, 1); }
/* Dispatch only the failing divide/shift slice; host I/O must never be reached. */
static uint32_t clip_divide(uint16_t entry);
const struct asm_module asm_modules[1] = {{0x06E7, 0x643A, 0x643D, clip_divide, "clip-divide"}};
const struct asm_glue asm_glues[1] = {{0}};
const struct asm_hand asm_hand_ranges[1] = {{0}};
const struct asm_hand_call asm_hand_calls[1] = {{0}};
const int asm_nmodules=1, asm_nglues=0, asm_nhand_ranges=0, asm_nhand_calls=0;
void *pm_segbase(unsigned seg) { abort(); }
void port_log(const char *fmt, ...) { abort(); }
uint8_t port_inb(unsigned port) { abort(); }
void port_outb(unsigned port, uint8_t value) { abort(); }
static uint32_t original_handler(void) {
'''
    code += handler + "\n}\n"
    # The failing divide and following shift, entered through the real near-call dispatcher.
    code += "static uint32_t clip_divide(uint16_t entry) { uint32_t c;\n"
    code += source[source.index("L643A:\n"):source.index("L643E:\n")]
    code += "SP = (uint16_t)(SP + 2); return ASM_RET;\n}\n"
    code += r'''
static void setup(unsigned sp, unsigned bp, unsigned flags) {
    pSS = stack;
    SP = sp; BP = bp; AX = 0x1234; DX = 0x5678;
    BX = 0xFF10; CX = 0; SI = 0xC8D; DI = 0x321;
    asm_set_flags(flags);
    ww(seg063, 0x4D5, 0x692C);
    ww(CODE004, 0x692A, 0xA55A);
    ww(CODE004, 0x5BCF, 123); /* this handler must not touch INSTANCE's counter */
}
int main(void) {
    /* Dump 20261026-221958: IDIV CX at 06E7:643A, CX=0, SP=043C.
       The original handles this; the missing native handler returned IRET to a near call. */
    for (unsigned sp = 0; sp < 0x10000; sp += 0x43C)
    for (unsigned bp = 0; bp < 0x10000; bp += 0x1111)
    for (unsigned bits = 0; bits < 32; bits++) {
        unsigned flags = 0x7202 | (bits&1) | ((bits>>1&1)<<6) | ((bits>>2&1)<<7)
                         | ((bits>>3&1)<<10) | ((bits>>4&1)<<11);
        setup(sp, bp, flags);
        assert(asm_idiv16(CX) == 1);
        push16(asm_flags()); push16(0x0EE7); push16(0x643A);
        assert(original_handler() == ASM_IRET);
        unsigned ax = AX, dx = DX, expected_flags = asm_flags();
        assert(SP == sp && BP == bp);
        assert(rw(stack, (uint16_t)(sp-6)) == 0x643C); /* resumes after the divide */
        assert(rw(CODE004, 0x692A) == bp);
        setup(sp, bp, flags);
        assert(asm_idiv16(CX) == 1);
        assert(asm_divfault(0x06E7, 0x643A, 2) == 0);
        assert(AX == ax && DX == dx && SP == sp && BP == bp && asm_flags() == expected_flags);
        assert(BX == 0xFF10 && CX == 0 && SI == 0xC8D && DI == 0x321);
        assert(rw(CODE004, 0x692A) == bp && rw(CODE004, 0x5BCF) == 123);
    }
    /* A nonzero divisor can overflow too; recovery must match the same handler. */
    setup(0x43C, 0x9876, 0x7242);
    DX = 0x7FFF; AX = 0xFFFF; CX = 1;
    assert(asm_idiv16(CX) == 1);
    assert(asm_divfault(0x06E7, 0x643A, 2) == 0);
    assert(AX == 0x7FFF && DX == 0 && SP == 0x43C && BP == 0x9876);
    setup(0x43E, 0x9876, 0x7242);
    assert(asm_call(ASM_JMP(0x06E7, 0x643A), 0x61C6) == 0);
    assert(AX == 0x3FFF && DX == 0 && SP == 0x43E && BP == 0x9876);
    /* Refuse instruction lengths for which DOS would resume in a different place. */
    if (!setjmp(halted)) { asm_divfault(0x06E7, 0x643A, 4); assert(0); }
    /* Preserve the existing frame-dropping handler path. */
    setup(0x43C, 0, 0x7242); ww(seg063, 0x4D5, 0x1234);
    assert(asm_divfault(0x06E7, 0x643A, 2) == ASM_JMP(0x06E7, 0x1234));
    assert(SP == 0x436 && rw(stack, SP) == 0x643A && rw(stack, SP+2) == 0x0EE7);
    puts("divfaultcheck: captured zero divisor, quotient overflow, all flags/stack wrap, original IRET equivalence and recovery dispatch passed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="uw1-divfault-") as tmp:
        work = Path(tmp)
        (work / "check.c").write_text(code)
        exe = work / ("check.exe" if os.name == "nt" else "check")
        subprocess.run([cc, "-std=c11",
                        "-I", str(ROOT / "src/port"), "-I", str(RUNTIME),
                        str(work / "check.c"), str(ROOT / "src/port/x86/divfault.c"),
                        str(RUNTIME / "x86/asmrt.c"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
