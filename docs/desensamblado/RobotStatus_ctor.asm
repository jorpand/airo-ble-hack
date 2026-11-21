# RobotStatus.ctor
# RVA 0x1fbde74 (file 0x1fb9e74)
# asigna el array: new byte[0x14] = 20 bytes

0x01fbde74  stp      x30, x21, [sp, #-0x20]!
0x01fbde78  stp      x20, x19, [sp, #0x10]
0x01fbde7c  adrp     x20, #0x4af4000
0x01fbde80  adrp     x21, #0x47c3000
0x01fbde84  mov      x19, x0
0x01fbde88  ldrb     w8, [x20, #0xef6]
0x01fbde8c  ldr      x21, [x21, #0x728]
0x01fbde90  tbnz     w8, #0, #0x1fbdea8
0x01fbde94  adrp     x0, #0x47c3000
0x01fbde98  ldr      x0, [x0, #0x728]
0x01fbde9c  bl       #0x1e21d38
0x01fbdea0  mov      w8, #1
0x01fbdea4  strb     w8, [x20, #0xef6]
0x01fbdea8  ldr      x0, [x21]
0x01fbdeac  mov      w1, #0x14
0x01fbdeb0  bl       #0x1e21e24
0x01fbdeb4  mov      x20, x19
0x01fbdeb8  mov      x1, x0
0x01fbdebc  str      x0, [x20, #0x10]!
0x01fbdec0  mov      x0, x20
0x01fbdec4  bl       #0x1e21ce4
0x01fbdec8  mov      x0, x19
0x01fbdecc  mov      x1, xzr
0x01fbded0  bl       #0x38c36d0
0x01fbded4  mov      x8, xzr
0x01fbded8  ldr      x9, [x20]
0x01fbdedc  cbz      x9, #0x1fbdf10
0x01fbdee0  ldr      w10, [x9, #0x18]
0x01fbdee4  cmp      x8, x10
0x01fbdee8  b.hs     #0x1fbdf14
0x01fbdeec  add      x9, x9, x8
0x01fbdef0  add      x8, x8, #1
0x01fbdef4  cmp      x8, #0x14
0x01fbdef8  strb     wzr, [x9, #0x20]
0x01fbdefc  b.ne     #0x1fbded8
0x01fbdf00  mov      x0, x19
0x01fbdf04  ldp      x20, x19, [sp, #0x10]
0x01fbdf08  ldp      x30, x21, [sp], #0x20
0x01fbdf0c  b        #0x1fbf968
0x01fbdf10  bl       #0x1e21fe0
0x01fbdf14  bl       #0x1e21fe8
0x01fbdf18  str      wzr, [x0, #0x64]
0x01fbdf1c  strb     wzr, [x0, #0x68]
0x01fbdf20  ret
