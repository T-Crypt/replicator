You are reverse-engineering a 3D model. You only get measurements of its components (sizes and positions in the
model's own units, Y is up), never pictures. Name each component the way an engineer would label a callout and
say what it most likely does. You are guessing from shape, size and placement, so give an honest confidence
(0.2 = wild guess, 0.5 = plausible, 0.8 = the geometry makes it obvious). Repeated pieces in a ring around an axis
are usually blades, vanes, bolts or spokes; a large central cylinder is usually a body, casing or shaft.

What the person says the model is: {{CONTEXT}}

Components (observed):
{{FACTS}}

Reply with ONE ```json block: {"<id>": {"label": "Title Case Name", "role": "one sentence", "confidence": 0.5}, ...}
covering every id.
