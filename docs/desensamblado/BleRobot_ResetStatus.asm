# BleRobot.ResetStatus
# RVA 0x1fbbc04 (file 0x1fb7c04)
# servos a 0

0x01fbbc04  str      x30, [sp, #-0x20]!
0x01fbbc08  stp      x20, x19, [sp, #0x10]
0x01fbbc0c  movi     d0, #0000000000000000
0x01fbbc10  mov      w20, w1
0x01fbbc14  mov      x19, x0
0x01fbbc18  bl       #0x1fbcbf4
0x01fbbc1c  movi     d0, #0000000000000000
0x01fbbc20  mov      x0, x19
0x01fbbc24  bl       #0x1fbce6c
0x01fbbc28  movi     d0, #0000000000000000
0x01fbbc2c  mov      x0, x19
0x01fbbc30  bl       #0x1fbd170
0x01fbbc34  movi     d0, #0000000000000000
0x01fbbc38  mov      x0, x19
0x01fbbc3c  bl       #0x1fbd474
0x01fbbc40  movi     d0, #0000000000000000
0x01fbbc44  mov      x0, x19
0x01fbbc48  bl       #0x1fbc7c8
0x01fbbc4c  movi     d0, #0000000000000000
0x01fbbc50  mov      x0, x19
0x01fbbc54  bl       #0x1fbc9b0
0x01fbbc58  tbz      w20, #0, #0x1fbbc74
0x01fbbc5c  ldr      x0, [x19, #0x40]
0x01fbbc60  cbz      x0, #0x1fbbc80
0x01fbbc64  ldp      x20, x19, [sp, #0x10]
0x01fbbc68  mov      w1, wzr
0x01fbbc6c  ldr      x30, [sp], #0x20
0x01fbbc70  b        #0x1fbcbc4
0x01fbbc74  ldp      x20, x19, [sp, #0x10]
0x01fbbc78  ldr      x30, [sp], #0x20
0x01fbbc7c  ret
