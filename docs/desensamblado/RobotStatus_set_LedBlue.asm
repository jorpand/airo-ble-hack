# RobotStatus.set_LedBlue
# RVA 0x1fbcbc4 (file 0x1fb8bc4)
# data[1]=estado del LED

0x01fbcbc4  str      x30, [sp, #-0x10]!
0x01fbcbc8  ldr      x8, [x0, #0x10]
0x01fbcbcc  str      w1, [x0, #0x30]
0x01fbcbd0  cbz      x8, #0x1fbcbec
0x01fbcbd4  ldr      w9, [x8, #0x18]
0x01fbcbd8  tst      w9, #0xfffffffe
0x01fbcbdc  b.eq     #0x1fbcbf0
0x01fbcbe0  strb     w1, [x8, #0x21]
0x01fbcbe4  ldr      x30, [sp], #0x10
0x01fbcbe8  ret
