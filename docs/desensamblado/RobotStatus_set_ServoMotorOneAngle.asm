# RobotStatus.set_ServoMotorOneAngle
# RVA 0x1fbcce0 (file 0x1fb8ce0)
# data[6]=servo1

0x01fbcce0  sub      sp, sp, #0x40
0x01fbcce4  str      d8, [sp, #0x10]
0x01fbcce8  str      x30, [sp, #0x18]
0x01fbccec  stp      x22, x21, [sp, #0x20]
0x01fbccf0  stp      x20, x19, [sp, #0x30]
0x01fbccf4  adrp     x21, #0x4af4000
0x01fbccf8  adrp     x22, #0x47c5000
0x01fbccfc  mov      w20, w1
0x01fbcd00  ldrb     w8, [x21, #0xef2]
0x01fbcd04  ldr      x22, [x22, #0x278]
0x01fbcd08  mov      x19, x0
0x01fbcd0c  tbnz     w8, #0, #0x1fbcd24
0x01fbcd10  adrp     x0, #0x47c5000
0x01fbcd14  ldr      x0, [x0, #0x278]
0x01fbcd18  bl       #0x1e21d38
0x01fbcd1c  mov      w8, #1
0x01fbcd20  strb     w8, [x21, #0xef2]
0x01fbcd24  ldr      x0, [x22]
0x01fbcd28  ldr      w8, [x0, #0xe4]
0x01fbcd2c  cbnz     w8, #0x1fbcd34
0x01fbcd30  bl       #0x1e21eb4
0x01fbcd34  adrp     x21, #0x4af4000
0x01fbcd38  ldrb     w8, [x21, #0xfb6]
0x01fbcd3c  cbnz     w8, #0x1fbcd60
0x01fbcd40  adrp     x0, #0x47c8000
0x01fbcd44  ldr      x0, [x0, #0x80]
0x01fbcd48  bl       #0x1e21d38
0x01fbcd4c  adrp     x0, #0x47c5000
0x01fbcd50  ldr      x0, [x0, #0x278]
0x01fbcd54  bl       #0x1e21d38
0x01fbcd58  mov      w8, #1
0x01fbcd5c  strb     w8, [x21, #0xfb6]
0x01fbcd60  mov      w9, #0x7f800000
0x01fbcd64  cmp      w20, #0x4d
0x01fbcd68  mov      w8, #0x4d
0x01fbcd6c  ldr      s0, [x19, #0x40]
0x01fbcd70  fmov     s1, w9
0x01fbcd74  csel     w8, w20, w8, lt
0x01fbcd78  cmn      w8, #0x3c
0x01fbcd7c  mov      w10, #-0x3c
0x01fbcd80  ldr      x20, [x19, #0x10]
0x01fbcd84  fcvtzs   w9, s0
0x01fbcd88  csel     w8, w8, w10, gt
0x01fbcd8c  mov      w10, #-0x80000000
0x01fbcd90  fcmp     s0, s1
0x01fbcd94  fmov     d1, #8.50000000
0x01fbcd98  add      x0, sp, #8
0x01fbcd9c  str      w8, [x19, #0x20]
0x01fbcda0  csel     w9, w10, w9, eq
0x01fbcda4  mov      w10, #0x154
0x01fbcda8  add      w9, w8, w9
0x01fbcdac  add      w9, w9, #0xaa
0x01fbcdb0  cmp      w9, #0x154
0x01fbcdb4  csel     w9, w9, w10, lt
0x01fbcdb8  bic      w9, w9, w9, asr #31
0x01fbcdbc  scvtf    s0, w9
0x01fbcdc0  fcvt     d0, s0
0x01fbcdc4  fdiv     d8, d0, d1
0x01fbcdc8  fmov     d0, d8
0x01fbcdcc  bl       #0x4547db0
0x01fbcdd0  fcmp     d8, #0.0
0x01fbcdd4  b.ge     #0x1fbcdf0
0x01fbcdd8  fmov     d1, #-0.50000000
0x01fbcddc  fcmp     d0, d1
0x01fbcde0  b.ne     #0x1fbce18
0x01fbcde4  ldr      d0, [sp, #8]
0x01fbcde8  fmov     d1, #-1.00000000
0x01fbcdec  b        #0x1fbce04
0x01fbcdf0  fmov     d1, #0.50000000
0x01fbcdf4  fcmp     d0, d1
0x01fbcdf8  b.ne     #0x1fbce24
0x01fbcdfc  fmov     d1, #1.00000000
0x01fbce00  ldr      d0, [sp, #8]
0x01fbce04  fcvtzs   x8, d0
0x01fbce08  fadd     d1, d0, d1
0x01fbce0c  tst      x8, #1
0x01fbce10  fcsel    d0, d0, d1, eq
0x01fbce14  b        #0x1fbce2c
0x01fbce18  fadd     d0, d8, d1
0x01fbce1c  frintp   d0, d0
0x01fbce20  b        #0x1fbce2c
0x01fbce24  fadd     d0, d8, d1
0x01fbce28  frintm   d0, d0
0x01fbce2c  cbz      x20, #0x1fbce64
0x01fbce30  ldr      w8, [x20, #0x18]
0x01fbce34  cmp      w8, #6
0x01fbce38  b.ls     #0x1fbce68
0x01fbce3c  fcvtzs   w8, d0
0x01fbce40  fcmp     d0, #0.0
0x01fbce44  ldr      x30, [sp, #0x18]
0x01fbce48  ldp      x22, x21, [sp, #0x20]
0x01fbce4c  ldr      d8, [sp, #0x10]
0x01fbce50  csel     w8, w8, w8, mi
0x01fbce54  strb     w8, [x20, #0x26]
0x01fbce58  ldp      x20, x19, [sp, #0x30]
0x01fbce5c  add      sp, sp, #0x40
0x01fbce60  ret
