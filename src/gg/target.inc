        CLOSE_KIND = 0x07
        CLOSE_BYTES = 64
        PAN_KIND = 0x08
        PAN_PORT = 0x06
        PAN_CENTRE = 0xFF
        .macro PAN_DISPATCH
        cp  a, #PAN_KIND
        jr  z, mvpan
        .endm
        .macro PAN_RUN
mvpan:
        inc hl
        ld  a, (hl)
        inc hl
        out (#PAN_PORT), a
        jp  mvloop
        .endm
        .macro PAN_RESET
        ld  a, #PAN_CENTRE
        out (#PAN_PORT), a
        .endm
