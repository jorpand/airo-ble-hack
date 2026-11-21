# AiroControl.set_LeftArmAngle
# RVA 0x1fb641c (file 0x1fb241c)
# brazo izquierdo -> SetThirdServoMotor

0x01fb641c  ldr      x0, [x0, #0x20]
0x01fb6420  cbz      x0, #0x1fb642c
0x01fb6424  mov      x1, xzr
0x01fb6428  b        #0x1fbd170
0x01fb642c  str      x30, [sp, #-0x10]!
0x01fb6430  bl       #0x1e21fe0
0x01fb6434  str      x30, [sp, #-0x10]!
0x01fb6438  ldr      x8, [x0, #0x20]
0x01fb643c  cbz      x8, #0x1fb6458
0x01fb6440  ldr      x8, [x8, #0x40]
0x01fb6444  cbz      x8, #0x1fb6458
0x01fb6448  ldr      s0, [x8, #0x20]
0x01fb644c  scvtf    s0, s0
0x01fb6450  ldr      x30, [sp], #0x10
0x01fb6454  ret
