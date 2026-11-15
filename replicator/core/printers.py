"""Printer profiles: the bed envelopes every print is gated against (FR-PR-12).

Bed volumes in CATALOG are the manufacturers' published figures, not measurements (section 5.9a of
docs/REQUIREMENTS-workbench.md): verify them on the device when it arrives, and let the tolerance test
print (FR-PR-10) refine each margin. Profiles live outside the repo, in services.json (`printers`:
catalog ids or hand-entered dicts, `active_printer`: one id). `transport` names how a job reaches the
machine: "file" is the export-only path, "bambu_lan" is Bambu's LAN mode (MQTT over TLS for status and
commands, files over FTPS behind the printer's access code).
"""
from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["Printer", "CATALOG", "configured", "active"]


@dataclass(frozen=True)
class Printer:
    """One bed, in millimetres. `bed_x`/`bed_y` span the bed plane, `height` the gantry, `nozzle` the
    nozzle width the scale-aware printability checks (FR-PR-15) will compare features against."""
    id: str
    name: str
    vendor: str
    bed_x: float
    bed_y: float
    height: float
    nozzle: float = 0.4
    margin: float = 2.0
    transport: str = "file"

    def usable(self) -> tuple[float, float, float]:
        """The build volume after safety margins: two on the bed plane (wall to wall), one on the height
        (the bed itself is the floor)."""
        return (self.bed_x - 2 * self.margin, self.bed_y - 2 * self.margin, self.height - self.margin)

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: dict) -> "Printer":
        """Parse a hand-entered profile from services.json; the defaults (nozzle, margin, transport) apply."""
        known = {f.name for f in fields(cls)}
        extra = set(d) - known
        if extra:
            raise ValueError(f"unknown printer fields {sorted(extra)}; use {sorted(known)}")
        missing = {"id", "name", "vendor", "bed_x", "bed_y", "height"} - set(d)
        if missing:
            raise ValueError(f"printer needs {sorted(missing)}")
        p = cls(**{k: d[k] for k in known if k in d})
        if not all(getattr(p, k) > 0 for k in ("bed_x", "bed_y", "height")):
            raise ValueError("bed_x, bed_y and height must be positive")
        if p.nozzle < 0 or p.margin < 0:
            raise ValueError("nozzle and margin must be non-negative")
        if 2 * p.margin >= min(p.bed_x, p.bed_y) or p.margin >= p.height:
            raise ValueError(f"margin {p.margin} leaves no usable volume on a {p.bed_x}x{p.bed_y}x{p.height} bed")
        return p


CATALOG: dict[str, Printer] = {p.id: p for p in (
    Printer("bambu_x1c", "X1 Carbon", "Bambu Lab", 256, 256, 256, transport="bambu_lan"),
    Printer("bambu_p1s", "P1S", "Bambu Lab", 256, 256, 256, transport="bambu_lan"),
    Printer("bambu_p1p", "P1P", "Bambu Lab", 256, 256, 256, transport="bambu_lan"),
    Printer("bambu_a1", "A1", "Bambu Lab", 256, 256, 256, transport="bambu_lan"),
    Printer("bambu_a1_mini", "A1 mini", "Bambu Lab", 180, 180, 180, transport="bambu_lan"),
    Printer("bambu_h2d", "H2D", "Bambu Lab", 350, 320, 325, transport="bambu_lan"),
)}


def configured(cfg: dict) -> list[Printer]:
    """The printers saved in services.json: catalog entries named by id plus custom dicts, in file order."""
    out: list[Printer] = []
    seen: set[str] = set()
    for entry in cfg.get("printers") or []:
        if isinstance(entry, str):
            p = CATALOG.get(entry)
            if p is None:
                raise ValueError(f"printer {entry!r} is not in the catalog or saved profiles")
        elif isinstance(entry, dict):
            p = Printer.from_dict(entry)
            if p.id in seen:
                raise ValueError(f"printer {p.id} is saved twice")
        else:
            raise ValueError(f"each entry of printers is a catalog id or a profile, not {type(entry).__name__}")
        out.append(p)
        seen.add(p.id)
    return out


def active(cfg: dict) -> Printer | None:
    """The active printer by its id (catalog, then saved profiles). None when unset or unknown: an
    unknown id must not break the status bar or the export path, which then runs printer-less."""
    aid = cfg.get("active_printer") or ""
    if not aid:
        return None
    if aid in CATALOG:
        return CATALOG[aid]
    for p in configured(cfg):
        if p.id == aid:
            return p
    return None
