# AiroControl.set_LeftShoulderAngle
# RVA 0x1fb63dc (file 0x1fb23dc)
# hombro izquierdo -> SetFourthServoMotor

0x01fb63dc  ldr      x0, [x0, #0x20]
0x01fb63e0  cbz      x0, #0x1fb63ec
0x01fb63e4  mov      x1, xzr
0x01fb63e8  b        #0x1fbd474
0x01fb63ec  str      x30, [sp, #-0x10]!
0x01fb63f0  bl       #0x1e21fe0
0x01fb63f4  str      x30, [sp, #-0x10]!
0x01fb63f8  ldr      x8, [x0, #0x20]
0x01fb63fc  cbz      x8, #0x1fb6418
0x01fb6400  ldr      x8, [x8, #0x40]
0x01fb6404  cbz      x8, #0x1fb6418
0x01fb6408  ldr      s0, [x8, #0x28]
0x01fb640c  scvtf    s0, s0
0x01fb6410  ldr      x30, [sp], #0x10
0x01fb6414  ret
