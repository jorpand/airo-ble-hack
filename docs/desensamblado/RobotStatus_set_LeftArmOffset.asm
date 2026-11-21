# RobotStatus.set_LeftArmOffset
# RVA 0x1fbd6f0 (file 0x1fb96f0)
# offset -> campo float, no byte del paquete

0x01fbd6f0  stp      d9, d8, [sp, #-0x30]!
0x01fbd6f4  str      x30, [sp, #0x10]
0x01fbd6f8  stp      x20, x19, [sp, #0x20]
0x01fbd6fc  fmov     s8, s0
0x01fbd700  adrp     x20, #0x4af4000
0x01fbd704  ldr      x19, [x0, #0x40]
0x01fbd708  ldrb     w8, [x20, #0xfb5]
0x01fbd70c  cbnz     w8, #0x1fbd724
0x01fbd710  adrp     x0, #0x47c5000
0x01fbd714  ldr      x0, [x0, #0x278]
0x01fbd718  bl       #0x1e21d38
0x01fbd71c  mov      w8, #1
0x01fbd720  strb     w8, [x20, #0xfb5]
0x01fbd724  adrp     x8, #0x47c5000
0x01fbd728  ldr      x8, [x8, #0x278]
0x01fbd72c  ldr      x0, [x8]
0x01fbd730  ldr      w8, [x0, #0xe4]
0x01fbd734  cbnz     w8, #0x1fbd73c
0x01fbd738  bl       #0x1e21eb4
0x01fbd73c  fcvt     d9, s8
0x01fbd740  add      x0, sp, #0x18
0x01fbd744  fmov     d0, d9
0x01fbd748  bl       #0x4547db0
0x01fbd74c  fcmp     s8, #0.0
0x01fbd750  b.ge     #0x1fbd76c
0x01fbd754  fmov     d1, #-0.50000000
0x01fbd758  fcmp     d0, d1
0x01fbd75c  b.ne     #0x1fbd794
0x01fbd760  ldr      d0, [sp, #0x18]
0x01fbd764  fmov     d1, #-1.00000000
0x01fbd768  b        #0x1fbd780
0x01fbd76c  fmov     d1, #0.50000000
0x01fbd770  fcmp     d0, d1
0x01fbd774  b.ne     #0x1fbd7a0
0x01fbd778  fmov     d1, #1.00000000
0x01fbd77c  ldr      d0, [sp, #0x18]
0x01fbd780  fcvtzs   x8, d0
0x01fbd784  fadd     d1, d0, d1
0x01fbd788  tst      x8, #1
0x01fbd78c  fcsel    d0, d0, d1, eq
0x01fbd790  b        #0x1fbd7a8
0x01fbd794  fadd     d0, d9, d1
0x01fbd798  frintp   d0, d0
0x01fbd79c  b        #0x1fbd7a8
0x01fbd7a0  fadd     d0, d9, d1
0x01fbd7a4  frintm   d0, d0
0x01fbd7a8  cbz      x19, #0x1fbd7dc
0x01fbd7ac  fcvtzs   w8, d0
0x01fbd7b0  mov      x9, #0x7ff0000000000000
0x01fbd7b4  movi     v3.2s, #0xcf, lsl #24
0x01fbd7b8  fmov     d2, x9
0x01fbd7bc  ldr      x30, [sp, #0x10]
0x01fbd7c0  scvtf    s1, w8
0x01fbd7c4  fcmp     d0, d2
0x01fbd7c8  fcsel    s0, s3, s1, eq
0x01fbd7cc  str      s0, [x19, #0x34]
0x01fbd7d0  ldp      x20, x19, [sp, #0x20]
0x01fbd7d4  ldp      d9, d8, [sp], #0x30
0x01fbd7d8  ret
