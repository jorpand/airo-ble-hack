# RobotStatus.set_RightMotorSpeed
# RVA 0x1fbca9c (file 0x1fb8a9c)
# data[2]=direccion der, data[3]=magnitud

0x01fbca9c  stp      x30, x21, [sp, #-0x20]!
0x01fbcaa0  stp      x20, x19, [sp, #0x10]
0x01fbcaa4  adrp     x21, #0x4af4000
0x01fbcaa8  mov      w19, w1
0x01fbcaac  mov      x20, x0
0x01fbcab0  ldrb     w8, [x21, #0xef0]
0x01fbcab4  tbnz     w8, #0, #0x1fbcacc
0x01fbcab8  adrp     x0, #0x47c5000
0x01fbcabc  ldr      x0, [x0, #0x278]
0x01fbcac0  bl       #0x1e21d38
0x01fbcac4  mov      w8, #1
0x01fbcac8  strb     w8, [x21, #0xef0]
0x01fbcacc  str      w19, [x20, #0x18]
0x01fbcad0  cbz      w19, #0x1fbcaf8
0x01fbcad4  ldr      x8, [x20, #0x10]
0x01fbcad8  cmp      w19, #1
0x01fbcadc  b.lt     #0x1fbcb2c
0x01fbcae0  cbz      x8, #0x1fbcb94
0x01fbcae4  ldr      w9, [x8, #0x18]
0x01fbcae8  cmp      w9, #2
0x01fbcaec  b.ls     #0x1fbcb98
0x01fbcaf0  mov      w9, #1
0x01fbcaf4  b        #0x1fbcb40
0x01fbcaf8  ldr      x8, [x20, #0x10]
0x01fbcafc  cbz      x8, #0x1fbcb94
0x01fbcb00  ldr      w9, [x8, #0x18]
0x01fbcb04  cmp      w9, #2
0x01fbcb08  b.ls     #0x1fbcb98
0x01fbcb0c  strb     wzr, [x8, #0x22]
0x01fbcb10  ldr      x20, [x20, #0x10]
0x01fbcb14  cbz      x20, #0x1fbcb94
0x01fbcb18  ldr      w8, [x20, #0x18]
0x01fbcb1c  tst      w8, #0xfffffffc
0x01fbcb20  b.eq     #0x1fbcb98
0x01fbcb24  mov      w0, wzr
0x01fbcb28  b        #0x1fbcb84
0x01fbcb2c  cbz      x8, #0x1fbcb94
0x01fbcb30  ldr      w9, [x8, #0x18]
0x01fbcb34  cmp      w9, #2
0x01fbcb38  b.ls     #0x1fbcb98
0x01fbcb3c  mov      w9, #2
0x01fbcb40  adrp     x10, #0x47c5000
0x01fbcb44  ldr      x10, [x10, #0x278]
0x01fbcb48  strb     w9, [x8, #0x22]
0x01fbcb4c  ldr      x20, [x20, #0x10]
0x01fbcb50  ldr      x0, [x10]
0x01fbcb54  ldr      w8, [x0, #0xe4]
0x01fbcb58  cbnz     w8, #0x1fbcb60
0x01fbcb5c  bl       #0x1e21eb4
0x01fbcb60  cmp      w19, #0
0x01fbcb64  mov      w1, #3
0x01fbcb68  mov      x2, xzr
0x01fbcb6c  cneg     w0, w19, mi
0x01fbcb70  bl       #0x38827b8
0x01fbcb74  cbz      x20, #0x1fbcb94
0x01fbcb78  ldr      w8, [x20, #0x18]
0x01fbcb7c  tst      w8, #0xfffffffc
0x01fbcb80  b.eq     #0x1fbcb98
0x01fbcb84  strb     w0, [x20, #0x23]
0x01fbcb88  ldp      x20, x19, [sp, #0x10]
0x01fbcb8c  ldp      x30, x21, [sp], #0x20
0x01fbcb90  ret
