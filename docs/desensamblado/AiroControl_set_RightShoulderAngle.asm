# AiroControl.set_RightShoulderAngle
# RVA 0x1fb645c (file 0x1fb245c)
# hombro derecho -> SetFirstServoMotor

0x01fb645c  ldr      x0, [x0, #0x20]
0x01fb6460  cbz      x0, #0x1fb646c
0x01fb6464  mov      x1, xzr
0x01fb6468  b        #0x1fbcbf4
0x01fb646c  str      x30, [sp, #-0x10]!
0x01fb6470  bl       #0x1e21fe0
0x01fb6474  str      x30, [sp, #-0x10]!
0x01fb6478  ldr      x8, [x0, #0x20]
0x01fb647c  cbz      x8, #0x1fb6498
0x01fb6480  ldr      x8, [x8, #0x40]
0x01fb6484  cbz      x8, #0x1fb6498
0x01fb6488  ldr      s0, [x8, #0x24]
0x01fb648c  scvtf    s0, s0
0x01fb6490  ldr      x30, [sp], #0x10
0x01fb6494  ret
