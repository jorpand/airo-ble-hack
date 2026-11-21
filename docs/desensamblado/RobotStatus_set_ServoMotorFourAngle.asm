# RobotStatus.set_ServoMotorFourAngle
# RVA 0x1fbd560 (file 0x1fb9560)
# data[9]=servo4

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
0x01fbd65c  fmov     d1, #-0.50000000
0x01fbd660  fcmp     d0, d1
0x01fbd664  b.ne     #0x1fbd69c
0x01fbd668  ldr      d0, [sp, #8]
0x01fbd66c  fmov     d1, #-1.00000000
0x01fbd670  b        #0x1fbd688
0x01fbd674  fmov     d1, #0.50000000
0x01fbd678  fcmp     d0, d1
0x01fbd67c  b.ne     #0x1fbd6a8
0x01fbd680  fmov     d1, #1.00000000
0x01fbd684  ldr      d0, [sp, #8]
0x01fbd688  fcvtzs   x8, d0
0x01fbd68c  fadd     d1, d0, d1
0x01fbd690  tst      x8, #1
0x01fbd694  fcsel    d0, d0, d1, eq
0x01fbd698  b        #0x1fbd6b0
0x01fbd69c  fadd     d0, d8, d1
0x01fbd6a0  frintp   d0, d0
0x01fbd6a4  b        #0x1fbd6b0
0x01fbd6a8  fadd     d0, d8, d1
0x01fbd6ac  frintm   d0, d0
0x01fbd6b0  cbz      x20, #0x1fbd6e8
0x01fbd6b4  ldr      w8, [x20, #0x18]
0x01fbd6b8  cmp      w8, #9
0x01fbd6bc  b.ls     #0x1fbd6ec
0x01fbd6c0  fcvtzs   w8, d0
0x01fbd6c4  fcmp     d0, #0.0
0x01fbd6c8  ldr      x30, [sp, #0x18]
0x01fbd6cc  ldp      x22, x21, [sp, #0x20]
0x01fbd6d0  ldr      d8, [sp, #0x10]
0x01fbd6d4  csel     w8, w8, w8, mi
0x01fbd6d8  strb     w8, [x20, #0x29]
0x01fbd6dc  ldp      x20, x19, [sp, #0x30]
0x01fbd6e0  add      sp, sp, #0x40
0x01fbd6e4  ret
