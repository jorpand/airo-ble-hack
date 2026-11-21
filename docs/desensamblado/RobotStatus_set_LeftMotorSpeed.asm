# RobotStatus.set_LeftMotorSpeed
# RVA 0x1fbc8b4 (file 0x1fb88b4)
# data[4]=direccion izq, data[5]=magnitud

0x01fbc8b4  stp      x30, x21, [sp, #-0x20]!
0x01fbc8b8  stp      x20, x19, [sp, #0x10]
0x01fbc8bc  adrp     x21, #0x4af4000
0x01fbc8c0  mov      w19, w1
0x01fbc8c4  mov      x20, x0
0x01fbc8c8  ldrb     w8, [x21, #0xef1]
0x01fbc8cc  tbnz     w8, #0, #0x1fbc8e4
0x01fbc8d0  adrp     x0, #0x47c5000
0x01fbc8d4  ldr      x0, [x0, #0x278]
0x01fbc8d8  bl       #0x1e21d38
0x01fbc8dc  mov      w8, #1
0x01fbc8e0  strb     w8, [x21, #0xef1]
0x01fbc8e4  str      w19, [x20, #0x1c]
0x01fbc8e8  cbz      w19, #0x1fbc90c
0x01fbc8ec  ldr      x8, [x20, #0x10]
0x01fbc8f0  tbnz     w19, #0x1f, #0x1fbc940
0x01fbc8f4  cbz      x8, #0x1fbc9a8
0x01fbc8f8  ldr      w9, [x8, #0x18]
0x01fbc8fc  cmp      w9, #4
0x01fbc900  b.ls     #0x1fbc9ac
0x01fbc904  mov      w9, #2
0x01fbc908  b        #0x1fbc954
0x01fbc90c  ldr      x8, [x20, #0x10]
0x01fbc910  cbz      x8, #0x1fbc9a8
0x01fbc914  ldr      w9, [x8, #0x18]
0x01fbc918  cmp      w9, #4
0x01fbc91c  b.ls     #0x1fbc9ac
0x01fbc920  strb     wzr, [x8, #0x24]
0x01fbc924  ldr      x20, [x20, #0x10]
0x01fbc928  cbz      x20, #0x1fbc9a8
0x01fbc92c  ldr      w8, [x20, #0x18]
0x01fbc930  cmp      w8, #5
0x01fbc934  b.ls     #0x1fbc9ac
0x01fbc938  mov      w0, wzr
0x01fbc93c  b        #0x1fbc998
0x01fbc940  cbz      x8, #0x1fbc9a8
0x01fbc944  ldr      w9, [x8, #0x18]
0x01fbc948  cmp      w9, #4
0x01fbc94c  b.ls     #0x1fbc9ac
0x01fbc950  mov      w9, #1
0x01fbc954  adrp     x10, #0x47c5000
0x01fbc958  ldr      x10, [x10, #0x278]
0x01fbc95c  strb     w9, [x8, #0x24]
0x01fbc960  ldr      x20, [x20, #0x10]
0x01fbc964  ldr      x0, [x10]
0x01fbc968  ldr      w8, [x0, #0xe4]
0x01fbc96c  cbnz     w8, #0x1fbc974
0x01fbc970  bl       #0x1e21eb4
0x01fbc974  cmp      w19, #0
0x01fbc978  mov      w1, #3
0x01fbc97c  mov      x2, xzr
0x01fbc980  cneg     w0, w19, mi
0x01fbc984  bl       #0x38827b8
0x01fbc988  cbz      x20, #0x1fbc9a8
0x01fbc98c  ldr      w8, [x20, #0x18]
0x01fbc990  cmp      w8, #5
0x01fbc994  b.ls     #0x1fbc9ac
0x01fbc998  strb     w0, [x20, #0x25]
0x01fbc99c  ldp      x20, x19, [sp, #0x10]
0x01fbc9a0  ldp      x30, x21, [sp], #0x20
0x01fbc9a4  ret
