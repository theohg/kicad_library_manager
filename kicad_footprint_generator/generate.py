import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from .pattern.qeda_pattern import QedaPattern
from .kicad_writer import write_kicad_mod


DEFAULT_SETTINGS = {
    'style': 'default',
    'densityLevel': 'N',
    'decimals': 3,
    'polarityMark': 'dot',
    'preferManufacturer': True,
    'smoothPadCorners': False,
    'tolerance': {
        'default': 0.1,
        'fabrication': 0.1,
        'placement': 0.1,
    },
    'clearance': {
        'padToSilk': 0.2,
        'silkToPad': 0.2,  # KiCad silk_pad_clearance
        'padToPad': 0.2,
        'padToMask': 0.0,
        'leadToHole': 0.1,
    },
    'ratio': {
        'padToHole': 1.5,
        'cornerToWidth': 0.25,
    },
    'minimum': {
        'ringWidth': 0.2,
        'holeDiameter': 0.2,
        'maskWidth': 0.2,
        'spaceForIron': 0,
    },
    'maximum': {
        'cornerRadius': 0.2,
    },
    'lineWidth': {
        'default': 0.2,
        'silkscreen': 0.12,
        'assembly': 0.1,
        'courtyard': 0.05,
    },
    'fontSize': {
        'default': 1,
        'refDes': 1.2,
        'value': 1,
    },
    'ball': {
        'collapsible': True,
    },
}


def build_pattern(kind: str, element: Dict[str, Any]) -> QedaPattern:
    settings = element.get('library', {}).get('pattern', DEFAULT_SETTINGS)
    decimals = settings.get('decimals', 3)
    # IMPORTANT:
    # Many builders only generate `pattern.description` / `pattern.tags` inside a guard like:
    #   if not getattr(pattern, "name", None): ...
    # The wx GUI often pre-sets element["name"] (name override), which previously prevented
    # those builders from populating description/tags.
    #
    # To keep name overrides working *and* still get auto description/tags, we let builders
    # run with an empty initial name, then re-apply the provided name after build.
    provided_name = str(element.get("name") or "").strip()
    pattern = QedaPattern(settings=settings, decimals=decimals, name="")
    # route to builder dynamically (import relative to this package)
    from importlib import import_module
    mod_name = f"{__package__}.pattern.default.{kind.lower()}"
    try:
        mod = import_module(mod_name)
        build = getattr(mod, 'build')
    except Exception as e:
        raise ValueError(f'Unsupported kind: {kind} ({e})')
    build(pattern, element)
    if provided_name:
        pattern.name = provided_name
    return pattern


def generate_footprint(kind: str, element: Dict[str, Any], out_dir: str) -> str:
    pattern = build_pattern(kind, element)
    # Allow UI to override the auto-generated description.
    description = element.get("description") or element.get("description_override") or getattr(pattern, 'description', None)
    tags = getattr(pattern, 'tags', None)
    content = write_kicad_mod(pattern.name, pattern.shapes, pattern.type, pattern.decimals, 
                             descr=description, tags=tags)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = os.path.join(out_dir, f"{pattern.name}.kicad_mod")
    # Atomic write (avoids partially-written files on overwrite).
    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=f".{pattern.name}.", suffix=".kicad_mod.tmp", dir=out_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, out_path)
        tmp_path = ""
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    return out_path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate KiCad .kicad_mod footprint (IPC-7351)')
    parser.add_argument('--kind', required=True, help='Footprint kind, e.g., soic, sot23, bga')
    parser.add_argument('--element', required=True, help='JSON file describing element and housing')
    parser.add_argument('--out', default='./kicad/footprints', help='Output directory (.pretty) or path')
    args = parser.parse_args()

    with open(args.element, 'r', encoding='utf-8') as f:
        element = json.load(f)
    path = generate_footprint(args.kind, element, args.out)
    print(path)

