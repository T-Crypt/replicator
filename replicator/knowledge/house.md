---
title: House and floor plan
keywords: house, home, floor plan, floorplan, bungalow, cabin, cottage, apartment, villa, building, rooms, bedroom, kitchen, residence, architecture
---
Orientation: the building stands on y = 0; X is width, Z is depth, front door on the +Z side. Millimetres.

Build it the way a plan is drawn: a floor slab, then walls as long thin boxes, then openings cut with boolean
difference (a door or window is a box subtracted from the wall it sits in), then the roof. Give every room's walls
or floor its own component named for the room, so the plan and the parts list read as rooms.

Typical dimensions (residential, conservative ranges):
- Floor slab 150 to 200 thick. Ceiling height 2400 to 2700 (finished floor to ceiling).
- Exterior walls 200 to 300 thick; interior partitions 100 to 120 thick.
- Interior doors 820 to 920 wide, 2040 to 2100 high; front door about 900 to 1000 wide.
- Windows: sill about 900 above the floor, head about 2100; typical widths 900 to 1800.
- Rooms: bedroom at least about 3000 x 3000 (main bedroom 3600 x 4000 or more); bathroom about 1800 x 2400 to
  2400 x 3000; kitchen at least about 2400 wide; living room about 4000 x 5000 or more; hallway 900 to 1200 wide.
- Stairs: riser 170 to 190, tread (going) 250 to 280, width at least 900.
- Pitched roof 20 to 45 degrees, eaves overhang 300 to 600; a flat roof has a parapet about 300 to 1000 high.
- A small single-storey house is often about 10 000 x 8000 to 15 000 x 10 000 overall.

Walls must meet at corners (overlap or butt them; never leave gaps), and every room needs a door into it.
