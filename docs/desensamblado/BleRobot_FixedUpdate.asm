# BleRobot.FixedUpdate
# RVA 0x1fbc688 (file 0x1fb8688)
# envio periodico del paquete + contador packageIdx

0x01fbc688  str      d8, [sp, #-0x30]!
0x01fbc68c  str      x30, [sp, #8]
0x01fbc690  stp      x22, x21, [sp, #0x10]
0x01fbc694  stp      x20, x19, [sp, #0x20]
0x01fbc698  adrp     x20, #0x4af4000
0x01fbc69c  mov      x19, x0
0x01fbc6a0  ldrb     w8, [x20, #0xedc]
0x01fbc6a4  tbnz     w8, #0, #0x1fbc6e0
0x01fbc6a8  adrp     x0, #0x47c4000
0x01fbc6ac  ldr      x0, [x0, #0xbd8]
0x01fbc6b0  bl       #0x1e21d38
0x01fbc6b4  adrp     x0, #0x47c8000
0x01fbc6b8  ldr      x0, [x0, #0x68]
0x01fbc6bc  bl       #0x1e21d38
0x01fbc6c0  adrp     x0, #0x47c8000
0x01fbc6c4  ldr      x0, [x0, #0x70]
0x01fbc6c8  bl       #0x1e21d38
0x01fbc6cc  adrp     x0, #0x47c8000
0x01fbc6d0  ldr      x0, [x0, #0x78]
0x01fbc6d4  bl       #0x1e21d38
0x01fbc6d8  mov      w8, #1
0x01fbc6dc  strb     w8, [x20, #0xedc]
0x01fbc6e0  ldrb     w8, [x19, #0x48]
0x01fbc6e4  cbz      w8, #0x1fbc7a4
0x01fbc6e8  ldrb     w8, [x19, #0x68]
0x01fbc6ec  cbnz     w8, #0x1fbc7a4
0x01fbc6f0  ldr      s8, [x19, #0x64]
0x01fbc6f4  mov      x0, xzr
0x01fbc6f8  bl       #0x421d874
0x01fbc6fc  fadd     s0, s8, s0
0x01fbc700  ldr      s1, [x19, #0x5c]
0x01fbc704  fcmp     s0, s1
0x01fbc708  str      s0, [x19, #0x64]
0x01fbc70c  b.le     #0x1fbc7a4
0x01fbc710  ldr      w9, [x19, #0x6c]
0x01fbc714  ldr      x8, [x19, #0x40]
0x01fbc718  mov      w10, #1
0x01fbc71c  strb     w10, [x19, #0x68]
0x01fbc720  add      w9, w9, #1
0x01fbc724  str      w9, [x19, #0x6c]
0x01fbc728  cbz      x8, #0x1fbc7b8
0x01fbc72c  adrp     x9, #0x47c4000
0x01fbc730  ldr      x9, [x9, #0xbd8]
0x01fbc734  ldr      x20, [x19, #0x50]
0x01fbc738  ldr      x21, [x8, #0x10]
0x01fbc73c  ldr      x0, [x9]
0x01fbc740  bl       #0x1e21fd0
0x01fbc744  adrp     x8, #0x47c8000
0x01fbc748  mov      x1, x19
0x01fbc74c  mov      x3, xzr
0x01fbc750  ldr      x8, [x8, #0x68]
0x01fbc754  mov      x22, x0
0x01fbc758  ldr      x2, [x8]
0x01fbc75c  bl       #0x2b07e28
0x01fbc760  adrp     x8, #0x47c8000
0x01fbc764  adrp     x9, #0x47c8000
0x01fbc768  mov      x0, x20
0x01fbc76c  ldr      x8, [x8, #0x70]
0x01fbc770  ldr      x9, [x9, #0x78]
0x01fbc774  mov      x3, x21
0x01fbc778  mov      x6, x22
0x01fbc77c  ldp      x20, x19, [sp, #0x20]
0x01fbc780  ldp      x22, x21, [sp, #0x10]
0x01fbc784  ldr      x1, [x8]
0x01fbc788  ldr      x2, [x9]
0x01fbc78c  ldr      x30, [sp, #8]
0x01fbc790  mov      w4, #0x14
0x01fbc794  mov      w5, wzr
0x01fbc798  mov      x7, xzr
0x01fbc79c  ldr      d8, [sp], #0x30
0x01fbc7a0  b        #0x1f1a4dc
0x01fbc7a4  ldp      x20, x19, [sp, #0x20]
0x01fbc7a8  ldr      x30, [sp, #8]
0x01fbc7ac  ldp      x22, x21, [sp, #0x10]
0x01fbc7b0  ldr      d8, [sp], #0x30
0x01fbc7b4  ret
