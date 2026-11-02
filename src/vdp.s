        .module vdp

        .globl _fmv_screen_table
        .globl _fmv_vdp_register
        .globl _fmv_vdp_fill

        .area _CODE

_fmv_screen_table::
        di
        out (#0xBF), a
        ld  a, #0x82
        nop
        nop
        nop
        out (#0xBF), a
        ei
        ret

_fmv_vdp_register::
        di
        out (#0xBF), a
        ld  a, l
        or  #0x80
        nop
        nop
        out (#0xBF), a
        ei
        ret

_fmv_vdp_fill::
        di
        ld  a, (hl)
        inc hl
        out (#0xBF), a
        ld  a, (hl)
        inc hl
        nop
        nop
        out (#0xBF), a
        ei
        ld  d, (hl)
        inc hl
        ld  e, (hl)
        inc hl
        ld  a, (hl)
        inc hl
        ld  h, (hl)
        ld  l, a
        ld  c, #0xBE
fmvvdpfill:
        out (c), d
        nop
        nop
        nop
        nop
        nop
        out (c), e
        dec hl
        ld  a, h
        or  l
        jp  nz, fmvvdpfill
        ret
