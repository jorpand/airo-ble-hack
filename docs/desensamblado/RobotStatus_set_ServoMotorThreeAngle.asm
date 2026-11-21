# RobotStatus.set_ServoMotorThreeAngle
# RVA 0x1fbd25c (file 0x1fb925c)
# data[8]=servo3

0x01fbd25c  sub      sp, sp, #0x40
0x01fbd260  str      d8, [sp, #0x10]
0x01fbd264  str      x30, [sp, #0x18]
0x01fbd268  stp      x22, x21, [sp, #0x20]
0x01fbd26c  stp      x20, x19, [sp, #0x30]
0x01fbd270  adrp     x21, #0x4af4000
0x01fbd274  mov      w20, w1
0x01fbd278  mov      x19, x0
0x01fbd27c  ldrb     w8, [x21, #0xef4]
0x01fbd280  tbnz     w8, #0, #0x1fbd298
0x01fbd284  adrp     x0, #0x47c5000
0x01fbd288  ldr      x0, [x0, #0x278]
0x01fbd28c  bl       #0x1e21d38
0x01fbd290  mov      w8, #1
0x01fbd294  strb     w8, [x21, #0xef4]
0x01fbd298  adrp     x21, #0x47c5000
0x01fbd29c  ldr      w8, [x19, #0x20]
0x01fbd2a0  ldr      x21, [x21, #0x278]
0x01fbd2a4  cbz      w8, #0x1fbd368
0x01fbd2a8  ldr      w8, [x19, #0x2c]
0x01fbd2ac  cbz      w8, #0x1fbd368
0x01fbd2b0  ldr      w8, [x19, #0x24]
0x01fbd2b4  sub      w8, w8, #1
0x01fbd2b8  cmn      w8, #0x24
0x01fbd2bc  b.le     #0x1fbd314
0x01fbd2c0  tbnz     w8, #0x1f, #0x1fbd368
0x01fbd2c4  ldr      x0, [x21]
0x01fbd2c8  ldr      w8, [x0, #0xe4]
0x01fbd2cc  cbnz     w8, #0x1fbd2d4
0x01fbd2d0  bl       #0x1e21eb4
0x01fbd2d4  adrp     x22, #0x4af4000
0x01fbd2d8  ldrb     w8, [x22, #0xfb6]
0x01fbd2dc  cbnz     w8, #0x1fbd300
0x01fbd2e0  adrp     x0, #0x47c8000
0x01fbd2e4  ldr      x0, [x0, #0x80]
0x01fbd2e8  bl       #0x1e21d38
0x01fbd2ec  adrp     x0, #0x47c5000
0x01fbd2f0  ldr      x0, [x0, #0x278]
0x01fbd2f4  bl       #0x1e21d38
0x01fbd2f8  mov      w8, #1
0x01fbd2fc  strb     w8, [x22, #0xfb6]
0x01fbd300  cmp      w20, #0xaa
0x01fbd304  mov      w8, #0xaa
0x01fbd308  csel     w8, w20, w8, lt
0x01fbd30c  bic      w20, w8, w8, asr #31
0x01fbd310  b        #0x1fbd368
0x01fbd314  ldr      x0, [x21]
0x01fbd318  ldr      w8, [x0, #0xe4]
0x01fbd31c  cbnz     w8, #0x1fbd324
0x01fbd320  bl       #0x1e21eb4
0x01fbd324  adrp     x22, #0x4af4000
0x01fbd328  ldrb     w8, [x22, #0xfb6]
0x01fbd32c  cbnz     w8, #0x1fbd350
0x01fbd330  adrp     x0, #0x47c8000
0x01fbd334  ldr      x0, [x0, #0x80]
0x01fbd338  bl       #0x1e21d38
0x01fbd33c  adrp     x0, #0x47c5000
0x01fbd340  ldr      x0, [x0, #0x278]
0x01fbd344  bl       #0x1e21d38
0x01fbd348  mov      w8, #1
0x01fbd34c  strb     w8, [x22, #0xfb6]
0x01fbd350  cmp      w20, #0xaa
0x01fbd354  mov      w8, #0xaa
0x01fbd358  mov      w9, #-0x19
0x01fbd35c  csel     w8, w20, w8, lt
0x01fbd360  cmn      w8, #0x19
0x01fbd364  csel     w20, w8, w9, gt
0x01fbd368  mov      w8, #0x7f800000
0x01fbd36c  ldr      s0, [x19, #0x34]
0x01fbd370  ldr      x0, [x21]
0x01fbd374  fmov     s1, w8
0x01fbd378  mov      w8, #-0x80000000
0x01fbd37c  ldr      x21, [x19, #0x10]
0x01fbd380  fcvtzs   w9, s0
0x01fbd384  str      w20, [x19, #0x28]
0x01fbd388  fcmp     s0, s1
0x01fbd38c  csel     w8, w8, w9, eq
0x01fbd390  mov      w9, #0x154
0x01fbd394  add      w8, w20, w8
0x01fbd398  add      w8, w8, #0xaa
0x01fbd39c  cmp      w8, #0x154
0x01fbd3a0  csel     w8, w8, w9, lt
0x01fbd3a4  bic      w8, w8, w8, asr #31
0x01fbd3a8  scvtf    s8, w8
0x01fbd3ac  ldr      w8, [x0, #0xe4]
0x01fbd3b0  cbnz     w8, #0x1fbd3b8
0x01fbd3b4  bl       #0x1e21eb4
0x01fbd3b8  fcvt     d0, s8
0x01fbd3bc  fmov     d1, #8.50000000
0x01fbd3c0  add      x0, sp, #8
0x01fbd3c4  fdiv     d8, d0, d1
0x01fbd3c8  fmov     d0, d8
0x01fbd3cc  bl       #0x4547db0
0x01fbd3d0  fcmp     d8, #0.0
0x01fbd3d4  b.ge     #0x1fbd3f0
0x01fbd3d8  fmov     d1, #-0.50000000
0x01fbd3dc  fcmp     d0, d1
0x01fbd3e0  b.ne     #0x1fbd418
0x01fbd3e4  ldr      d0, [sp, #8]
0x01fbd3e8  fmov     d1, #-1.00000000
0x01fbd3ec  b        #0x1fbd404
0x01fbd3f0  fmov     d1, #0.50000000
0x01fbd3f4  fcmp     d0, d1
0x01fbd3f8  b.ne     #0x1fbd424
0x01fbd3fc  fmov     d1, #1.00000000
0x01fbd400  ldr      d0, [sp, #8]
0x01fbd404  fcvtzs   x8, d0
0x01fbd408  fadd     d1, d0, d1
0x01fbd40c  tst      x8, #1
0x01fbd410  fcsel    d0, d0, d1, eq
0x01fbd414  b        #0x1fbd42c
0x01fbd418  fadd     d0, d8, d1
0x01fbd41c  frintp   d0, d0
0x01fbd420  b        #0x1fbd42c
0x01fbd424  fadd     d0, d8, d1
0x01fbd428  frintm   d0, d0
0x01fbd42c  cbz      x21, #0x1fbd46c
0x01fbd430  ldr      w8, [x21, #0x18]
0x01fbd434  cmp      w8, #8
0x01fbd438  b.ls     #0x1fbd470
0x01fbd43c  fcvtzs   w8, d0
0x01fbd440  fcmp     d0, #0.0
0x01fbd444  mov      x0, x19
0x01fbd448  ldr      x30, [sp, #0x18]
0x01fbd44c  ldr      d8, [sp, #0x10]
0x01fbd450  csel     w8, w8, w8, mi
0x01fbd454  strb     w8, [x21, #0x28]
0x01fbd458  ldp      x22, x21, [sp, #0x20]
0x01fbd45c  ldr      w1, [x19, #0x2c]
0x01fbd460  ldp      x20, x19, [sp, #0x30]
0x01fbd464  add      sp, sp, #0x40
0x01fbd468  b        #0x1fbd560
0x01fbd46c  bl       #0x1e21fe0
0x01fbd470  bl       #0x1e21fe8
0x01fbd474  stp      d9, d8, [sp, #-0x30]!
0x01fbd478  str      x30, [sp, #0x10]
0x01fbd47c  stp      x20, x19, [sp, #0x20]
0x01fbd480  fmov     s8, s0
0x01fbd484  adrp     x20, #0x4af4000
0x01fbd488  ldr      x19, [x0, #0x40]
0x01fbd48c  ldrb     w8, [x20, #0xfb5]
0x01fbd490  cbnz     w8, #0x1fbd4a8
0x01fbd494  adrp     x0, #0x47c5000
0x01fbd498  ldr      x0, [x0, #0x278]
0x01fbd49c  bl       #0x1e21d38
0x01fbd4a0  mov      w8, #1
0x01fbd4a4  strb     w8, [x20, #0xfb5]
0x01fbd4a8  adrp     x8, #0x47c5000
0x01fbd4ac  ldr      x8, [x8, #0x278]
0x01fbd4b0  ldr      x0, [x8]
0x01fbd4b4  ldr      w8, [x0, #0xe4]
0x01fbd4b8  cbnz     w8, #0x1fbd4c0
0x01fbd4bc  bl       #0x1e21eb4
0x01fbd4c0  fcvt     d9, s8
0x01fbd4c4  add      x0, sp, #0x18
0x01fbd4c8  fmov     d0, d9
0x01fbd4cc  bl       #0x4547db0
0x01fbd4d0  fcmp     s8, #0.0
0x01fbd4d4  b.ge     #0x1fbd4f0
0x01fbd4d8  fmov     d1, #-0.50000000
0x01fbd4dc  fcmp     d0, d1
0x01fbd4e0  b.ne     #0x1fbd518
0x01fbd4e4  ldr      d0, [sp, #0x18]
0x01fbd4e8  fmov     d1, #-1.00000000
0x01fbd4ec  b        #0x1fbd504
0x01fbd4f0  fmov     d1, #0.50000000
0x01fbd4f4  fcmp     d0, d1
0x01fbd4f8  b.ne     #0x1fbd524
0x01fbd4fc  fmov     d1, #1.00000000
0x01fbd500  ldr      d0, [sp, #0x18]
0x01fbd504  fcvtzs   x8, d0
0x01fbd508  fadd     d1, d0, d1
0x01fbd50c  tst      x8, #1
0x01fbd510  fcsel    d0, d0, d1, eq
0x01fbd514  b        #0x1fbd52c
0x01fbd518  fadd     d0, d9, d1
0x01fbd51c  frintp   d0, d0
0x01fbd520  b        #0x1fbd52c
0x01fbd524  fadd     d0, d9, d1
0x01fbd528  frintm   d0, d0
0x01fbd52c  cbz      x19, #0x1fbd55c
0x01fbd530  mov      x8, #0x7ff0000000000000
0x01fbd534  fcvtzs   w9, d0
0x01fbd538  mov      x0, x19
0x01fbd53c  fmov     d1, x8
0x01fbd540  ldp      x20, x19, [sp, #0x20]
0x01fbd544  mov      w8, #-0x80000000
0x01fbd548  ldr      x30, [sp, #0x10]
0x01fbd54c  fcmp     d0, d1
0x01fbd550  csel     w1, w8, w9, eq
0x01fbd554  ldp      d9, d8, [sp], #0x30
0x01fbd558  b        #0x1fbd560
0x01fbd55c  bl       #0x1e21fe0
0x01fbd560  sub      sp, sp, #0x40
0x01fbd564  str      d8, [sp, #0x10]
0x01fbd568  str      x30, [sp, #0x18]
0x01fbd56c  stp      x22, x21, [sp, #0x20]
0x01fbd570  stp      x20, x19, [sp, #0x30]
0x01fbd574  adrp     x21, #0x4af4000
0x01fbd578  adrp     x22, #0x47c5000
0x01fbd57c  mov      w20, w1
0x01fbd580  ldrb     w8, [x21, #0xef5]
0x01fbd584  ldr      x22, [x22, #0x278]
0x01fbd588  mov      x19, x0
0x01fbd58c  tbnz     w8, #0, #0x1fbd5a4
0x01fbd590  adrp     x0, #0x47c5000
0x01fbd594  ldr      x0, [x0, #0x278]
0x01fbd598  bl       #0x1e21d38
0x01fbd59c  mov      w8, #1
0x01fbd5a0  strb     w8, [x21, #0xef5]
0x01fbd5a4  ldr      x0, [x22]
0x01fbd5a8  ldr      w8, [x0, #0xe4]
0x01fbd5ac  cbnz     w8, #0x1fbd5b4
0x01fbd5b0  bl       #0x1e21eb4
0x01fbd5b4  adrp     x21, #0x4af4000
0x01fbd5b8  ldrb     w8, [x21, #0xfb6]
0x01fbd5bc  cbnz     w8, #0x1fbd5e0
0x01fbd5c0  adrp     x0, #0x47c8000
0x01fbd5c4  ldr      x0, [x0, #0x80]
0x01fbd5c8  bl       #0x1e21d38
0x01fbd5cc  adrp     x0, #0x47c5000
0x01fbd5d0  ldr      x0, [x0, #0x278]
0x01fbd5d4  bl       #0x1e21d38
0x01fbd5d8  mov      w8, #1
0x01fbd5dc  strb     w8, [x21, #0xfb6]
0x01fbd5e0  mov      w9, #0x7f800000
0x01fbd5e4  cmp      w20, #0x4d
0x01fbd5e8  mov      w8, #0x4d
0x01fbd5ec  ldr      s0, [x19, #0x3c]
0x01fbd5f0  fmov     s1, w9
0x01fbd5f4  csel     w8, w20, w8, lt
0x01fbd5f8  cmn      w8, #0x3c
0x01fbd5fc  mov      w10, #-0x3c
0x01fbd600  mov      w9, #-0x80000000
0x01fbd604  fcvtzs   w11, s0
0x01fbd608  csel     w8, w8, w10, gt
0x01fbd60c  mov      w10, #0xaa
0x01fbd610  fcmp     s0, s1
0x01fbd614  sub      w10, w10, w8
0x01fbd618  fmov     d1, #8.50000000
0x01fbd61c  ldr      x20, [x19, #0x10]
0x01fbd620  add      x0, sp, #8
0x01fbd624  str      w8, [x19, #0x2c]
0x01fbd628  csel     w9, w9, w11, eq
0x01fbd62c  sub      w9, w10, w9
0x01fbd630  mov      w10, #0x154
0x01fbd634  cmp      w9, #0x154
0x01fbd638  csel     w9, w9, w10, lt
0x01fbd63c  bic      w9, w9, w9, asr #31
0x01fbd640  scvtf    s0, w9
0x01fbd644  fcvt     d0, s0
0x01fbd648  fdiv     d8, d0, d1
0x01fbd64c  fmov     d0, d8
0x01fbd650  bl       #0x4547db0
0x01fbd654  fcmp     d8, #0.0
0x01fbd658  b.ge     #0x1fbd674
