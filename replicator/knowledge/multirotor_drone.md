---
title: Multirotor drone
keywords: drone, quadcopter, quadrotor, multirotor, hexacopter, octocopter, fpv, uav, uas
---
Orientation: the drone is flat in the XZ plane, up is +Y, front is +Z. Propellers spin around Y, so `cylinder` and `tube` ops need no rotation.

Layout (quad X, the usual one): four motors on the corners of a square, arms running diagonally from a central body. Frame size is the diagonal motor-to-motor distance. Neighbouring motors must be at least one propeller diameter apart, so the diagonal is at least 1.41 times the prop diameter; real frames leave a 10 to 25 % margin.

Frame size by propeller (typical):
- 3 inch prop (76 mm): 120 to 150 mm frame.
- 5 inch prop (127 mm): 210 to 250 mm.
- 7 inch prop (178 mm): 295 to 330 mm.
- 10 inch prop (254 mm): 450 to 500 mm.
- 15 inch prop (381 mm): 650 to 800 mm.

Motors: named by stator size, so 2306 is a 23 mm wide, 6 mm tall stator; the bell is a few mm wider and about 30 mm tall overall. Motors spin alternately clockwise and counter-clockwise around the square. Typical KV: 5 inch on 4S to 6S, 1700 to 2700 KV; 7 inch on 6S, 1300 to 1700 KV; 10 inch on 4S, 700 to 1000 KV; 15 inch on 6S, 300 to 500 KV. A larger prop needs a lower KV.

Parts:
- Arms: carbon-fibre plate 3 to 5 mm thick (5 inch) or tube 12 to 25 mm (large frames), bolted to a centre plate.
- Centre plates: two parallel plates 15 to 30 mm apart carrying the stack; the flight controller and the 4-in-1 ESC board sit on a 30.5 x 30.5 mm bolt pattern (20 x 20 mm on small frames), each board about 36 mm square.
- Battery: a LiPo brick (4S 1300 to 1500 mAh, about 150 to 200 g, 75 x 35 x 30 mm) on the centre line, under or on top of the plates, so the centre of gravity sits at the middle of the motor square. Heavy payloads hang below.
- ESCs: on the stack for small drones, or one per arm near the motor on large ones; the flight controller is the middle of the stack.
- Camera or gimbal at the front, antennas on short mounts at the back, landing legs or a skid under the centre.

Weight: a 5 inch freestyle drone is about 600 to 700 g with its battery; thrust is at least twice the weight.
