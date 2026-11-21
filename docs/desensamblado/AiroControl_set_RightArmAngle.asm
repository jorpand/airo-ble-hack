# AiroControl.set_RightArmAngle
# RVA 0x1fb649c (file 0x1fb249c)
# brazo derecho -> SetSecondServoMotor

0x01fb649c  ldr      x0, [x0, #0x20]
0x01fb64a0  cbz      x0, #0x1fb64ac
0x01fb64a4  mov      x1, xzr
0x01fb64a8  b        #0x1fbce6c
0x01fb64ac  str      x30, [sp, #-0x10]!
0x01fb64b0  bl       #0x1e21fe0
0x01fb64b4  str      x30, [sp, #-0x10]!
0x01fb64b8  ldr      x8, [x0, #0x20]
0x01fb64bc  cbz      x8, #0x1fb64d4
0x01fb64c0  ldr      x8, [x8, #0x40]
0x01fb64c4  cbz      x8, #0x1fb64d4
0x01fb64c8  ldr      s0, [x8, #0x34]
0x01fb64cc  ldr      x30, [sp], #0x10
0x01fb64d0  ret
