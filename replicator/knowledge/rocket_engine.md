---
title: Liquid rocket engine
keywords: rocket, rocket engine, thruster, thrust chamber, nozzle, bell nozzle, turbopump, raptor, merlin, rs-25, f-1, rl10, booster engine, vacuum engine, liquid engine, regenerative
---
Orientation: rocket engines stand along Y, injector at the top, nozzle exit at the bottom. Do not lay them along Z.

Parts, top to bottom:
- Gimbal mount: a ball or cardan joint on the centre line above the injector, carrying all the thrust into the vehicle.
- Thrust frame: struts or a cone from the gimbal down to the injector dome.
- Injector and dome: a domed manifold capping the chamber; the flat injector face below it has hundreds of small elements.
- Combustion chamber: a short cylinder, wider than the throat, regeneratively cooled (fuel runs through channels in the wall).
- Throat: the narrowest point; everything is sized from its radius Rt.
- Bell nozzle: a parabolic (Rao) bell, about 80 % the length of a 15 degree cone with the same exit. Use the `nozzle` op: it draws chamber, throat and bell from `throat_radius`, `expansion_ratio` and `contraction_ratio`.
- Coolant manifold: a torus-like ring around the nozzle where fuel enters the cooling channels (often at the end of the regen section).
- Turbopump: beside the chamber, off the centre line. One shaft carries a turbine, a fuel pump and an oxidizer pump; each pump has a spiral volute (a torus-shaped casing) with a large inlet along the shaft and an outlet tangent to the volute. Its overall size is roughly the chamber diameter.
- Gas generator or preburner: a small chamber next to the turbopump that drives the turbine. Gas-generator engines dump the turbine exhaust through a separate exhaust duct beside the bell.
- Feed lines: large ducts from the pump outlets to the injector dome and to the coolant manifold, bent with smooth radii (`pipe`). Inlet ducts from the vehicle's tanks come down into the pump inlets.
- Main valves on the feed lines near the injector; two gimbal actuators (hydraulic or electric cylinders) 90 degrees apart, from the thrust frame to the chamber.

Proportions (typical ranges):
- Expansion ratio (exit area / throat area): sea-level engines 10 to 30, vacuum engines 40 to 200 and more. Exit radius = Rt * sqrt(expansion_ratio).
- Contraction ratio (chamber area / throat area): 1.5 to 5 on large engines, higher on small ones.
- Characteristic chamber length L* (chamber volume / throat area): about 0.8 to 1.3 m.
- Reference engines: F-1 is about 5.8 m tall with a 3.7 m exit and expansion ratio 16. RS-25 is about 4.3 m long with a 2.4 m exit and expansion ratio 69.
- Walls are thin compared with the size: a few millimetres of metal on a nozzle a metre across.

Materials: copper alloy chamber liner, nickel alloy or stainless jacket and nozzle, Inconel turbine, dark heat-tinted nozzle extension, foil thermal blankets.
