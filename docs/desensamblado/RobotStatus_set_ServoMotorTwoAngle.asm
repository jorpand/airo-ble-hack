# RobotStatus.set_ServoMotorTwoAngle
# RVA 0x1fbcf58 (file 0x1fb8f58)
# data[7]=servo2

0x01fbcf58  sub      sp, sp, #0x40
0x01fbcf5c  str      d8, [sp, #0x10]
0x01fbcf60  str      x30, [sp, #0x18]
0x01fbcf64  stp      x22, x21, [sp, #0x20]
0x01fbcf68  stp      x20, x19, [sp, #0x30]
0x01fbcf6c  adrp     x21, #0x4af4000
0x01fbcf70  mov      w20, w1
0x01fbcf74  mov      x19, x0
0x01fbcf78  ldrb     w8, [x21, #0xef3]
0x01fbcf7c  tbnz     w8, #0, #0x1fbcf94
0x01fbcf80  adrp     x0, #0x47c5000
0x01fbcf84  ldr      x0, [x0, #0x278]
0x01fbcf88  bl       #0x1e21d38
0x01fbcf8c  mov      w8, #1
0x01fbcf90  strb     w8, [x21, #0xef3]
0x01fbcf94  adrp     x21, #0x47c5000
0x01fbcf98  ldr      w8, [x19, #0x20]
0x01fbcf9c  ldr      x21, [x21, #0x278]
0x01fbcfa0  cbz      w8, #0x1fbd060
0x01fbcfa4  ldr      w8, [x19, #0x2c]
0x01fbcfa8  cbz      w8, #0x1fbd060
0x01fbcfac  ldr      w8, [x19, #0x28]
0x01fbcfb0  cmp      w8, #0x23
0x01fbcfb4  b.ge     #0x1fbd00c
0x01fbcfb8  tbz      w8, #0x1f, #0x1fbd060
0x01fbcfbc  ldr      x0, [x21]
0x01fbcfc0  ldr      w8, [x0, #0xe4]
0x01fbcfc4  cbnz     w8, #0x1fbcfcc
0x01fbcfc8  bl       #0x1e21eb4
0x01fbcfcc  adrp     x22, #0x4af4000
0x01fbcfd0  ldrb     w8, [x22, #0xfb6]
0x01fbcfd4  cbnz     w8, #0x1fbcff8
0x01fbcfd8  adrp     x0, #0x47c8000
0x01fbcfdc  ldr      x0, [x0, #0x80]
0x01fbcfe0  bl       #0x1e21d38
0x01fbcfe4  adrp     x0, #0x47c5000
0x01fbcfe8  ldr      x0, [x0, #0x278]
0x01fbcfec  bl       #0x1e21d38
0x01fbcff0  mov      w8, #1
0x01fbcff4  strb     w8, [x22, #0xfb6]
0x01fbcff8  cmp      w20, #0xaa
0x01fbcffc  mov      w8, #0xaa
0x01fbd000  csel     w8, w20, w8, lt
0x01fbd004  bic      w20, w8, w8, asr #31
0x01fbd008  b        #0x1fbd060
0x01fbd00c  ldr      x0, [x21]
0x01fbd010  ldr      w8, [x0, #0xe4]
0x01fbd014  cbnz     w8, #0x1fbd01c
0x01fbd018  bl       #0x1e21eb4
0x01fbd01c  adrp     x22, #0x4af4000
0x01fbd020  ldrb     w8, [x22, #0xfb6]
0x01fbd024  cbnz     w8, #0x1fbd048
0x01fbd028  adrp     x0, #0x47c8000
0x01fbd02c  ldr      x0, [x0, #0x80]
0x01fbd030  bl       #0x1e21d38
0x01fbd034  adrp     x0, #0x47c5000
0x01fbd038  ldr      x0, [x0, #0x278]
0x01fbd03c  bl       #0x1e21d38
0x01fbd040  mov      w8, #1
0x01fbd044  strb     w8, [x22, #0xfb6]
0x01fbd048  cmp      w20, #0xaa
0x01fbd04c  mov      w8, #0xaa
0x01fbd050  mov      w9, #-0x19
0x01fbd054  csel     w8, w20, w8, lt
0x01fbd058  cmn      w8, #0x19
0x01fbd05c  csel     w20, w8, w9, gt
0x01fbd060  mov      w8, #0x7f800000
0x01fbd064  ldr      s0, [x19, #0x38]
0x01fbd068  mov      w10, #0xaa
0x01fbd06c  fmov     s1, w8
0x01fbd070  mov      w8, #-0x80000000
0x01fbd074  ldr      x0, [x21]
0x01fbd078  fcvtzs   w9, s0
0x01fbd07c  ldr      x21, [x19, #0x10]
0x01fbd080  str      w20, [x19, #0x24]
0x01fbd084  fcmp     s0, s1
0x01fbd088  csel     w8, w8, w9, eq
0x01fbd08c  sub      w9, w10, w20
0x01fbd090  sub      w8, w9, w8
0x01fbd094  mov      w9, #0x154
0x01fbd098  cmp      w8, #0x154
0x01fbd09c  csel     w8, w8, w9, lt
0x01fbd0a0  bic      w8, w8, w8, asr #31
0x01fbd0a4  scvtf    s8, w8
0x01fbd0a8  ldr      w8, [x0, #0xe4]
0x01fbd0ac  cbnz     w8, #0x1fbd0b4
0x01fbd0b0  bl       #0x1e21eb4
0x01fbd0b4  fcvt     d0, s8
0x01fbd0b8  fmov     d1, #8.50000000
0x01fbd0bc  add      x0, sp, #8
0x01fbd0c0  fdiv     d8, d0, d1
0x01fbd0c4  fmov     d0, d8
0x01fbd0c8  bl       #0x4547db0
0x01fbd0cc  fcmp     d8, #0.0
0x01fbd0d0  b.ge     #0x1fbd0ec
0x01fbd0d4  fmov     d1, #-0.50000000
0x01fbd0d8  fcmp     d0, d1
0x01fbd0dc  b.ne     #0x1fbd114
0x01fbd0e0  ldr      d0, [sp, #8]
0x01fbd0e4  fmov     d1, #-1.00000000
0x01fbd0e8  b        #0x1fbd100
0x01fbd0ec  fmov     d1, #0.50000000
0x01fbd0f0  fcmp     d0, d1
0x01fbd0f4  b.ne     #0x1fbd120
0x01fbd0f8  fmov     d1, #1.00000000
0x01fbd0fc  ldr      d0, [sp, #8]
0x01fbd100  fcvtzs   x8, d0
0x01fbd104  fadd     d1, d0, d1
0x01fbd108  tst      x8, #1
0x01fbd10c  fcsel    d0, d0, d1, eq
0x01fbd110  b        #0x1fbd128
0x01fbd114  fadd     d0, d8, d1
0x01fbd118  frintp   d0, d0
0x01fbd11c  b        #0x1fbd128
0x01fbd120  fadd     d0, d8, d1
0x01fbd124  frintm   d0, d0
0x01fbd128  cbz      x21, #0x1fbd168
0x01fbd12c  ldr      w8, [x21, #0x18]
0x01fbd130  tst      w8, #0xfffffff8
0x01fbd134  b.eq     #0x1fbd16c
0x01fbd138  fcvtzs   w8, d0
0x01fbd13c  fcmp     d0, #0.0
0x01fbd140  mov      x0, x19
0x01fbd144  ldr      x30, [sp, #0x18]
0x01fbd148  ldr      d8, [sp, #0x10]
0x01fbd14c  csel     w8, w8, w8, mi
0x01fbd150  strb     w8, [x21, #0x27]
0x01fbd154  ldp      x22, x21, [sp, #0x20]
0x01fbd158  ldr      w1, [x19, #0x20]
0x01fbd15c  ldp      x20, x19, [sp, #0x30]
0x01fbd160  add      sp, sp, #0x40
0x01fbd164  b        #0x1fbcce0
0x01fbd168  bl       #0x1e21fe0
0x01fbd16c  bl       #0x1e21fe8
0x01fbd170  stp      d9, d8, [sp, #-0x30]!
0x01fbd174  str      x30, [sp, #0x10]
0x01fbd178  stp      x20, x19, [sp, #0x20]
0x01fbd17c  fmov     s8, s0
0x01fbd180  adrp     x20, #0x4af4000
0x01fbd184  ldr      x19, [x0, #0x40]
0x01fbd188  ldrb     w8, [x20, #0xfb5]
0x01fbd18c  cbnz     w8, #0x1fbd1a4
0x01fbd190  adrp     x0, #0x47c5000
0x01fbd194  ldr      x0, [x0, #0x278]
0x01fbd198  bl       #0x1e21d38
0x01fbd19c  mov      w8, #1
0x01fbd1a0  strb     w8, [x20, #0xfb5]
0x01fbd1a4  adrp     x8, #0x47c5000
0x01fbd1a8  ldr      x8, [x8, #0x278]
0x01fbd1ac  ldr      x0, [x8]
0x01fbd1b0  ldr      w8, [x0, #0xe4]
0x01fbd1b4  cbnz     w8, #0x1fbd1bc
0x01fbd1b8  bl       #0x1e21eb4
0x01fbd1bc  fcvt     d9, s8
0x01fbd1c0  add      x0, sp, #0x18
0x01fbd1c4  fmov     d0, d9
0x01fbd1c8  bl       #0x4547db0
0x01fbd1cc  fcmp     s8, #0.0
0x01fbd1d0  b.ge     #0x1fbd1ec
0x01fbd1d4  fmov     d1, #-0.50000000
0x01fbd1d8  fcmp     d0, d1
0x01fbd1dc  b.ne     #0x1fbd214
0x01fbd1e0  ldr      d0, [sp, #0x18]
0x01fbd1e4  fmov     d1, #-1.00000000
0x01fbd1e8  b        #0x1fbd200
0x01fbd1ec  fmov     d1, #0.50000000
0x01fbd1f0  fcmp     d0, d1
0x01fbd1f4  b.ne     #0x1fbd220
0x01fbd1f8  fmov     d1, #1.00000000
0x01fbd1fc  ldr      d0, [sp, #0x18]
0x01fbd200  fcvtzs   x8, d0
0x01fbd204  fadd     d1, d0, d1
0x01fbd208  tst      x8, #1
0x01fbd20c  fcsel    d0, d0, d1, eq
0x01fbd210  b        #0x1fbd228
0x01fbd214  fadd     d0, d9, d1
0x01fbd218  frintp   d0, d0
0x01fbd21c  b        #0x1fbd228
0x01fbd220  fadd     d0, d9, d1
0x01fbd224  frintm   d0, d0
0x01fbd228  cbz      x19, #0x1fbd258
0x01fbd22c  mov      x8, #0x7ff0000000000000
0x01fbd230  fcvtzs   w9, d0
0x01fbd234  mov      x0, x19
0x01fbd238  fmov     d1, x8
0x01fbd23c  ldp      x20, x19, [sp, #0x20]
0x01fbd240  mov      w8, #-0x80000000
0x01fbd244  ldr      x30, [sp, #0x10]
0x01fbd248  fcmp     d0, d1
0x01fbd24c  csel     w1, w8, w9, eq
0x01fbd250  ldp      d9, d8, [sp], #0x30
0x01fbd254  b        #0x1fbd25c
0x01fbd258  bl       #0x1e21fe0
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
