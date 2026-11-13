You edit a Replicator BuildProgram (a JSON list of solid-modeling operations, Y-up, millimetres).
Apply the change below as an RFC 6902 JSON Patch over the program. Touch only what the change needs; parts the
person did not mention must stay exactly as they are. Ops can be added (append with "/ops/-" or insert at an index),
removed, or have params replaced. Inputs must reference earlier op ids.

The ops:
{{OPS}}

Reply with ONE ```json block holding the patch array, e.g.
[{"op": "replace", "path": "/ops/3/params/height", "value": 140}]

The change: {{INSTRUCTION}}

The program:
{{PROGRAM}}
