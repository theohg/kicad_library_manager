from __future__ import annotations

import os
from dataclasses import dataclass
from math import ceil, sqrt
from typing import Dict, Optional


@dataclass
class Range:
    min: float
    max: float
    nom: Optional[float] = None


def _density_value(map_: Dict[str, float], density: str) -> float:
    return map_[density]


# KiCad's embedded Python environment may have stdout/stderr in a state where printing
# raises `OSError: [Errno 9] Bad file descriptor`. This module historically had many
# debug `print(...)` statements; make them safe and disabled by default.
#
# Enable by setting KICAD_LIBRARY_MANAGER_FPGEN_DEBUG=1 in the environment.
import builtins as _builtins  # noqa: E402

_DEBUG = bool(str(os.environ.get("KICAD_LIBRARY_MANAGER_FPGEN_DEBUG", "")).strip())


def _safe_print(*args, **kwargs) -> None:  # noqa: ANN001
    if not _DEBUG:
        return
    try:
        _builtins.print(*args, **kwargs)
    except OSError:
        return
    except Exception:
        return


# Override module-local `print` used by legacy debug statements.
print = _safe_print  # type: ignore[assignment]


def _round(x: float, step: float) -> float:
    return round(x / step) * step if step else x


def _ceil_to(x: float, step: float) -> float:
    return ceil(x / step) * step if step else x


def _ipc7351(params: dict) -> dict:
    Lmin = params['Lmin']
    Lmax = params['Lmax']
    Ltol = Lmax - Lmin
    Tmin = params['Tmin']
    Tmax = params['Tmax']
    Ttol = Tmax - Tmin
    Wmin = params['Wmin']
    Wmax = params['Wmax']
    Wtol = Wmax - Wmin

    F = params['F']
    P = params['P']
    Jt = params['Jt']
    Jh = params['Jh']
    Js = params['Js']

    Smin = Lmin - 2 * Tmax
    Smax = Lmax - 2 * Tmin
    Stol = Ltol + 2 * Ttol
    StolRms = sqrt(Ltol * Ltol + 2 * Ttol * Ttol)
    SmaxRms = Smax - (Stol - StolRms) / 2

    Cl = Ltol
    Cs = StolRms
    Cw = Wtol

    print(f"Lmin: {Lmin}, Lmax: {Lmax}, Ltol: {Ltol}, Tmin: {Tmin}, Tmax: {Tmax}, Ttol: {Ttol}, Wmin: {Wmin}, Wmax: {Wmax}, Wtol: {Wtol}, F: {F}, P: {P}, Jt: {Jt}, Jh: {Jh}, Js: {Js}, Smin: {Smin}, Smax: {Smax}, Stol: {Stol}, StolRms: {StolRms}, SmaxRms: {SmaxRms}, Cl: {Cl}, Cs: {Cs}, Cw: {Cw}")

    return {
        'Zmax': Lmin + 2 * Jt + sqrt(Cl * Cl + F * F + P * P),
        'Gmin': SmaxRms - 2 * Jh - sqrt(Cs * Cs + F * F + P * P),
        'Xmax': Wmin + 2 * Js + sqrt(Cw * Cw + F * F + P * P),
    }


def _pad(ipc: dict, pattern: dict) -> dict:
    pad_width = (ipc['Zmax'] - ipc['Gmin']) / 2
    pad_height = ipc['Xmax']
    pad_distance = (ipc['Zmax'] + ipc['Gmin']) / 2
    
    print(f"DEBUG _pad: Zmax={ipc['Zmax']:.3f}, Gmin={ipc['Gmin']:.3f}, Xmax={ipc['Xmax']:.3f}")
    print(f"DEBUG _pad: pad_width={pad_width:.3f}, pad_height={pad_height:.3f}, pad_distance={pad_distance:.3f}")

    size_roundoff = pattern.get('sizeRoundoff', 0.05)
    place_roundoff = pattern.get('placeRoundoff', 0.1)
    pad_width_rounded = _round(pad_width, size_roundoff)
    pad_height_rounded = _round(pad_height, size_roundoff)
    pad_distance_rounded = _round(pad_distance, place_roundoff)
    
    print(f"DEBUG _pad: After rounding (size:{size_roundoff}, place:{place_roundoff})")
    print(f"DEBUG _pad: pad_width {pad_width:.3f} -> {pad_width_rounded:.3f}")
    print(f"DEBUG _pad: pad_height {pad_height:.3f} -> {pad_height_rounded:.3f}")
    print(f"DEBUG _pad: pad_distance {pad_distance:.3f} -> {pad_distance_rounded:.3f}")
    
    pad_width = pad_width_rounded
    pad_height = pad_height_rounded
    pad_distance = pad_distance_rounded

    gap = pad_distance - pad_width
    span = pad_distance + pad_width
    trimmed = False

    if 'clearance' in ipc and gap < ipc['clearance']:
        gap = ipc['clearance']
        trimmed = True

    if 'body' in ipc and gap < (ipc['body'] - 0.1):
        gap = ipc['body'] - 0.1
        trimmed = True

    if trimmed:
        pad_width = (span - gap) / 2
        pad_distance = (span + gap) / 2
        pad_distance = _ceil_to(pad_distance, place_roundoff)

    if 'pitch' in ipc and pad_height > (ipc['pitch'] - ipc['clearance']):
        pad_height = ipc['pitch'] - ipc['clearance']
        trimmed = True

    return {
        'width': pad_width,
        'height': pad_height,
        'distance': pad_distance,
        'trimmed': trimmed,
    }


def _params(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    return {
        'Tmin': housing['leadLength']['min'],
        'Tmax': housing['leadLength']['max'],
        'Wmin': housing['leadWidth']['min'],
        'Wmax': housing['leadWidth']['max'],
        'F': settings['tolerance']['fabrication'],
        'P': settings['tolerance']['placement'],
        'courtyard': pattern.get('courtyard', {'M': 0.5, 'N': 0.25, 'L': 0.12}[settings['densityLevel']]),
    }


def _choose_preferred(pad: dict, pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    if settings.get('preferManufacturer'):
        if 'padWidth' in housing:
            pad['width'] = housing['padWidth']
            if 'padSpace' in housing:
                pad['distance'] = housing['padSpace'] + housing['padWidth']
            if 'padSpan' in housing:
                pad['distance'] = housing['padSpan'] - housing['padWidth']
        if 'padWidth1' in housing:
            pad['width1'] = housing['padWidth1']
            if 'padSpace' in housing:
                pad['distance1'] = housing['padSpace'] + housing['padWidth1']
            if 'padSpace1' in housing:
                pad['distance1'] = housing['padSpace1'] + housing['padWidth1']
            if 'padSpan' in housing:
                pad['distance1'] = housing['padSpan'] - housing['padWidth1']
            if 'padSpan1' in housing:
                pad['distance1'] = housing['padSpan1'] - housing['padWidth1']
        if 'padWidth2' in housing:
            pad['width2'] = housing['padWidth2']
            if 'padSpace' in housing:
                pad['distance2'] = housing['padSpace'] + housing['padWidth2']
            if 'padSpace2' in housing:
                pad['distance2'] = housing['padSpace2'] + housing['padWidth2']
            if 'padSpan' in housing:
                pad['distance2'] = housing['padSpan'] - housing['padWidth2']
            if 'padSpan2' in housing:
                pad['distance2'] = housing['padSpan2'] - housing['padWidth2']

        if 'padHeight' in housing:
            pad['height'] = housing['padHeight']
        if 'padHeight1' in housing:
            pad['height1'] = housing['padHeight1']
        if 'padHeight2' in housing:
            pad['height2'] = housing['padHeight2']

        if 'padDistance' in housing:
            pad['distance'] = housing['padDistance']
        if 'padDistance1' in housing:
            pad['distance1'] = housing['padDistance1']
        if 'padDistance2' in housing:
            pad['distance2'] = housing['padDistance2']

        if 'holeDiameter' in housing:
            pad['hole'] = housing['holeDiameter']
    return pad


def _gullwing(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    pitch = housing['pitch']
    
    # IPC-7351 Gullwing packages: pitch-based toe/heel/side/courtyard per user table
    if pitch > 1.00:
        # Pitch > 1.00 mm
        toes = {'L': 0.30, 'N': 0.35, 'M': 0.40}
        heels = {'L': 0.40, 'N': 0.45, 'M': 0.50}
        sides = {'L': 0.05, 'N': 0.06, 'M': 0.07}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.80:
        # Pitch > 0.80 and <= 1.00 mm
        toes = {'L': 0.25, 'N': 0.30, 'M': 0.35}
        heels = {'L': 0.35, 'N': 0.40, 'M': 0.45}
        sides = {'L': 0.04, 'N': 0.05, 'M': 0.06}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.65:
        # Pitch > 0.65 and <= 0.80 mm
        toes = {'L': 0.20, 'N': 0.25, 'M': 0.30}
        heels = {'L': 0.30, 'N': 0.35, 'M': 0.40}
        sides = {'L': 0.03, 'N': 0.04, 'M': 0.05}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.50:
        # Pitch > 0.50 and <= 0.65 mm
        toes = {'L': 0.15, 'N': 0.20, 'M': 0.25}
        heels = {'L': 0.25, 'N': 0.30, 'M': 0.35}
        sides = {'L': 0.01, 'N': 0.02, 'M': 0.03}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.40:
        # Pitch > 0.40 and <= 0.50 mm
        toes = {'L': 0.10, 'N': 0.15, 'M': 0.20}
        heels = {'L': 0.20, 'N': 0.25, 'M': 0.30}
        sides = {'L': 0.00, 'N': 0.00, 'M': 0.00}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    else:
        # Pitch <= 0.40 mm
        toes = {'L': 0.10, 'N': 0.15, 'M': 0.20}
        heels = {'L': 0.20, 'N': 0.25, 'M': 0.30}
        sides = {'L': 0.00, 'N': 0.00, 'M': 0.00}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Jh'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    params['courtyard'] = courtyard
    # Round to 0.05 mm grid for pad sizes per table note
    pattern['sizeRoundoff'] = 0.05
    return params


def _flatlead(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    toes = {'M': 0.3, 'N': 0.2, 'L': 0.1}
    heels = {'M': 0.0, 'N': 0.0, 'L': 0.0}
    sides = {'M': 0.05, 'N': 0.0, 'L': -0.05}
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Jh'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    # IPC-7351 Table 3-22: smaller courtyard for SODFL/SOTFL; round-off 0.05
    params['courtyard'] = {'M': 0.20, 'N': 0.15, 'L': 0.10}[settings['densityLevel']]
    pattern['sizeRoundoff'] = 0.05
    return params


def _sotfl_flatlead(pattern: dict, housing: dict) -> dict:
    """SOTFL-specific flatlead parameters with custom density values"""
    settings = pattern['settings']
    # Custom density parameters for SOTFL as specified by user
    toes = {'M': 0.3, 'N': 0.2, 'L': 0.1}
    heels = {'M': 0.0, 'N': 0.0, 'L': 0.0}
    sides = {'M': 0.05, 'N': 0.0, 'L': 0.0}
    courtyard_values = {'M': 0.4, 'N': 0.2, 'L': 0.1}
    
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Jh'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    params['courtyard'] = courtyard_values[settings['densityLevel']]
    pattern['sizeRoundoff'] = 0.05
    return params


def _jlead(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    toes = {'M': 0.1, 'N': 0.0, 'L': -0.1}
    heels = {'M': 0.55, 'N': 0.35, 'L': 0.15}
    sides = {'M': 0.05, 'N': 0.03, 'L': 0.01}
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Jh'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    params['courtyard'] = {'M': 0.50, 'N': 0.25, 'L': 0.10}[settings['densityLevel']]
    pattern['sizeRoundoff'] = 0.05
    return params


def _soj_jlead(pattern: dict, housing: dict) -> dict:
    """SOJ-specific J-lead parameters with custom density values"""
    settings = pattern['settings']
    # Custom density parameters for SOJ as specified by user
    toes = {'M': 0.1, 'N': 0.0, 'L': 0.0}
    heels = {'M': 0.55, 'N': 0.35, 'L': 0.15}
    sides = {'M': 0.05, 'N': 0.03, 'L': 0.01}
    courtyard_values = {'M': 0.4, 'N': 0.2, 'L': 0.1}
    
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Jh'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    params['courtyard'] = courtyard_values[settings['densityLevel']]
    pattern['sizeRoundoff'] = 0.05
    return params


def _llead(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    toes = {'M': 0.1, 'N': 0.0, 'L': -0.1}
    heels = {'M': 0.55, 'N': 0.35, 'L': 0.15}
    sides = {'M': 0.01, 'N': -0.02, 'L': -0.04}
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Jh'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    return params


def _nolead(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    # Check if pullBack exists AND is non-zero
    pullback_value = 0
    if 'pullBack' in housing:
        if isinstance(housing['pullBack'], dict):
            pullback_value = housing['pullBack'].get('nom', 0)
        else:
            pullback_value = housing['pullBack']
    
    if pullback_value != 0:
        # Table 3-18 for pullback no-lead (PSON, QPFN, DFN with pullback)
        periphery = {'M': 0.05, 'N': 0.0, 'L': -0.05}[settings['densityLevel']]
        toe = periphery
        heel = 0.0
        side = periphery
        # Round-off and courtyard per table
        pattern['sizeRoundoff'] = 0.05
    else:
        # DFN/SON/QFN without pullback use periphery per body length thresholds
        # Per user table: periphery A and courtyard depend on body length and density
        bl_nom = 0.0
        try:
            bl_nom = float(housing.get('bodyLength', {}).get('nom', 0.0))
        except Exception:
            bl_nom = 0.0

        dl = settings['densityLevel']
        # Periphery A
        if dl == 'M':
            periphery = 0.05 if bl_nom >= 1.60 else 0.00
        elif dl == 'N':
            periphery = 0.00
        else:  # 'L'
            periphery = 0.00

        toe = periphery
        heel = 0.0
        side = periphery
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('toe', toe)
    params['Jh'] = pattern.get('heel', heel)
    params['Js'] = pattern.get('side', side)
    # Courtyard per table depends on body length
    bl_nom = 0.0
    try:
        bl_nom = float(housing.get('bodyLength', {}).get('nom', 0.0))
    except Exception:
        bl_nom = 0.0
    dl = settings['densityLevel']
    if dl == 'M':
        courtyard = 0.40 if bl_nom >= 1.60 else 0.20
    elif dl == 'N':
        courtyard = 0.20 if bl_nom >= 1.60 else 0.15
    else:  # 'L'
        courtyard = 0.10
    params['courtyard'] = courtyard
    return params


def dual(pattern: dict, housing: dict, option: str) -> dict:
    settings = pattern['settings']
    if option == 'flatlead':
        params = _flatlead(pattern, housing)
    elif option == 'soj':
        params = _jlead(pattern, housing)
    elif option == 'sol':
        params = _llead(pattern, housing)
    elif option == 'sop':
        params = _gullwing(pattern, housing)
    else:
        raise ValueError('Unsupported dual option')

    params['Lmin'] = housing['leadSpan']['min']
    params['Lmax'] = housing['leadSpan']['max']
    ipc = _ipc7351(params)
    ipc['clearance'] = settings['clearance']['padToPad']
    ipc['pitch'] = housing['pitch']
    if option == 'sop':
        ipc['body'] = housing['bodyWidth']['nom']
    pad = _pad(ipc, pattern)
    pad['courtyard'] = params['courtyard']
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad = (pad['distance'] + pad['width'] - housing['leadSpan']['nom']) / 2
    if lead_to_pad < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad
        pad['width'] += d
        pad['distance'] += d
    return pad


def grid_array(pattern: dict, housing: dict, option: str) -> dict:
    settings = pattern['settings']
    pad_diameter = None  # ensure defined for all branches
    if option == 'bga':
        # IPC-7351 Table 3-17
        collapsible = settings.get('ball', {}).get('collapsible', False)
        dl = settings['densityLevel']
        ld = housing['leadDiameter']
        lead_nom = ld['nom'] if isinstance(ld, dict) else ld
        if collapsible:
            # Reduction below nominal diameter
            factors = {'M': 0.75, 'N': 0.80, 'L': 0.85}
        else:
            # Increase above nominal diameter
            factors = {'M': 1.15, 'N': 1.10, 'L': 1.05}
        pad_diameter = lead_nom * factors[dl]
        # Respect pitch clearance if provided
        pitch = housing.get('pitch')
        if pitch:
            clearance = housing.get('padSpace', settings['clearance']['padToPad'])
            if pad_diameter > pitch - clearance:
                pad_diameter = pitch - clearance
        # Round to 0.05 mm per table note
        pattern['sizeRoundoff'] = 0.05
        pad_diameter = _round(pad_diameter, pattern['sizeRoundoff'])
        courtyard = {'M': 2.00, 'N': 1.00, 'L': 0.50}[dl]
    elif option == 'cga':
        # IPC-7351 Table 3-21: Periphery 0.00, round-off 0.05, courtyard 1.00
        pad_diameter = housing['leadDiameter']['nom']
        pitch = housing.get('pitch', min(housing['horizontalPitch'], housing['verticalPitch']))
        clearance = housing.get('padSpace', settings['clearance']['padToPad'])
        if pad_diameter > pitch - clearance:
            pad_diameter = pitch - clearance
        pattern['sizeRoundoff'] = 0.05
        pad_diameter = _round(pad_diameter, pattern['sizeRoundoff'])
        courtyard = 1.00
    elif option == 'lga':
        # IPC-7351 Table 3-21: Periphery 0.00, round-off 0.05, courtyard 1.00
        clearance = housing.get('padSpace', settings['clearance']['padToPad'])
        pad_width = housing['leadLength']['nom']
        horizontal_pitch = housing.get('horizontalPitch', housing.get('pitch'))
        if pad_width > horizontal_pitch - clearance:
            pad_width = horizontal_pitch - clearance
        lw = housing.get('leadWidth')
        if isinstance(lw, dict):
            lw_nom = lw.get('nom', lw.get('max', lw.get('min', 0)))
        else:
            lw_nom = float(lw or 0)
        pad_height = lw_nom
        vertical_pitch = housing.get('verticalPitch', housing.get('pitch'))
        if pad_height > vertical_pitch - clearance:
            pad_height = vertical_pitch - clearance
        pattern['sizeRoundoff'] = 0.05
        pad_width = _round(pad_width, pattern['sizeRoundoff'])
        pad_height = _round(pad_height, pattern['sizeRoundoff'])
        courtyard = 1.00
    else:
        raise ValueError('Unsupported grid array option')

    pad_width = locals().get('pad_width') or pad_diameter
    pad_height = locals().get('pad_height') or pad_diameter
    pad = {'width': pad_width, 'height': pad_height, 'courtyard': courtyard}
    return _choose_preferred(pad, pattern, housing)


def chip_array(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    housing.setdefault('leadSpan', housing['bodyWidth'])
    toes = {'M': 0.55, 'N': 0.45, 'L': 0.35}
    heels = {'M': -0.05, 'N': -0.07, 'L': -0.10}
    sides = {'M': -0.05, 'N': -0.07, 'L': -0.10}
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Jh'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    # Courtyard per concave table and round-off factor note
    params['courtyard'] = {'M': 0.50, 'N': 0.25, 'L': 0.10}[settings['densityLevel']]
    pattern['sizeRoundoff'] = 0.05
    params['Lmin'] = housing['leadSpan']['min']
    params['Lmax'] = housing['leadSpan']['max']
    ipc = _ipc7351(params)
    ipc['clearance'] = settings['clearance']['padToPad']
    ipc['pitch'] = housing['pitch']
    pad = _pad(ipc, pattern)
    pad['courtyard'] = params['courtyard']
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad = (pad['distance'] + pad['width'] - housing['leadSpan']['nom']) / 2
    if lead_to_pad < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad
        pad['width'] += d
        pad['distance'] += d
    return pad


def corner_concave(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    
    # Convert datasheet parameters to internal format if needed
    # Corner concave oscillators typically provide:
    # - bodyWidth/bodyLength (package dimensions)
    # - padSeparationLength/Width (edge-to-edge pad separation)
    # We need to derive leadLength/Width and rowSpan/columnSpan from these
    
    def _extract_values(param):
        """Extract min/nom/max values from dict or scalar"""
        if isinstance(param, dict):
            return {
                'min': param.get('min', param.get('nom', param.get('max', 0))),
                'nom': param.get('nom', param.get('max', param.get('min', 0))),
                'max': param.get('max', param.get('nom', param.get('min', 0)))
            }
        val = float(param or 0)
        return {'min': val, 'nom': val, 'max': val}
    
    # Extract body dimensions with tolerances
    body_length = _extract_values(housing.get('bodyLength', 0))
    body_width = _extract_values(housing.get('bodyWidth', 0))
    
    # Handle pad separation parameters with proper tolerance propagation
    print(f"DEBUG corner_concave: input housing keys: {housing.keys()}")
    print(f"DEBUG corner_concave: body_length = {body_length}")
    print(f"DEBUG corner_concave: body_width = {body_width}")
    
    # Fixed mapping: padSeparationLength -> rowSpan, padSeparationWidth -> columnSpan
    if 'padSeparationLength' in housing:
        pad_sep_length = _extract_values(housing['padSeparationLength'])
        print(f"DEBUG corner_concave: padSeparationLength = {pad_sep_length}")
        
        # Lead length = (body_length - pad_separation) / 2
        # Proper tolerance propagation for lead dimension
        lead_length_min = max(0.05, (body_length['min'] - pad_sep_length['max']) / 2)
        lead_length_nom = max(0.05, (body_length['nom'] - pad_sep_length['nom']) / 2)
        lead_length_max = max(0.05, (body_length['max'] - pad_sep_length['min']) / 2)
        
        # Lead span (center-to-center) = (body_length + pad_separation) / 2
        # This is the distance between pad centers
        row_span_min = (body_length['min'] + pad_sep_length['min']) / 2
        row_span_nom = (body_length['nom'] + pad_sep_length['nom']) / 2
        row_span_max = (body_length['max'] + pad_sep_length['max']) / 2
        
        print(f"DEBUG corner_concave: calculated rowSpan = min:{row_span_min}, nom:{row_span_nom}, max:{row_span_max}")
        print(f"DEBUG corner_concave: calculated leadLength = min:{lead_length_min}, nom:{lead_length_nom}, max:{lead_length_max}")
        
        housing.setdefault('rowSpan', {
            'min': row_span_min,
            'nom': row_span_nom,
            'max': row_span_max
        })
        housing.setdefault('leadLength', {
            'min': lead_length_min, 
            'nom': lead_length_nom, 
            'max': lead_length_max
        })
    
    if 'padSeparationWidth' in housing:
        pad_sep_width = _extract_values(housing['padSeparationWidth'])
        print(f"DEBUG corner_concave: padSeparationWidth = {pad_sep_width}")
        
        # Lead width = (body_width - pad_separation) / 2  
        # Proper tolerance propagation for lead dimension
        lead_width_min = max(0.05, (body_width['min'] - pad_sep_width['max']) / 2)
        lead_width_nom = max(0.05, (body_width['nom'] - pad_sep_width['nom']) / 2)
        lead_width_max = max(0.05, (body_width['max'] - pad_sep_width['min']) / 2)
        
        # Lead span (center-to-center) = (body_width + pad_separation) / 2
        # This is the distance between pad centers  
        col_span_min = (body_width['min'] + pad_sep_width['min']) / 2
        col_span_nom = (body_width['nom'] + pad_sep_width['nom']) / 2
        col_span_max = (body_width['max'] + pad_sep_width['max']) / 2
        
        print(f"DEBUG corner_concave: calculated columnSpan = min:{col_span_min}, nom:{col_span_nom}, max:{col_span_max}")
        print(f"DEBUG corner_concave: calculated leadWidth = min:{lead_width_min}, nom:{lead_width_nom}, max:{lead_width_max}")
        
        housing.setdefault('columnSpan', {
            'min': col_span_min,
            'nom': col_span_nom,
            'max': col_span_max
        })
        housing.setdefault('leadWidth', {
            'min': lead_width_min,
            'nom': lead_width_nom, 
            'max': lead_width_max
        })
    
    # If no pad separation provided, estimate from body dimensions (fallback)
    if 'rowSpan' not in housing and body_length['nom'] > 0:
        # Assume leads take up ~20% of body length each, separation is ~60%
        est_lead_length = body_length['nom'] * 0.2
        est_pad_sep = body_length['nom'] * 0.6
        housing.setdefault('rowSpan', {'nom': est_pad_sep + est_lead_length})
        housing.setdefault('leadLength', {'nom': est_lead_length, 'min': est_lead_length * 0.8, 'max': est_lead_length * 1.2})
    
    if 'columnSpan' not in housing and body_width['nom'] > 0:
        est_lead_width = body_width['nom'] * 0.2
        est_pad_sep = body_width['nom'] * 0.6
        housing.setdefault('columnSpan', {'nom': est_pad_sep + est_lead_width})
        housing.setdefault('leadWidth', {'nom': est_lead_width, 'min': est_lead_width * 0.8, 'max': est_lead_width * 1.2})
    
    # IPC-7351 Corner Concave Oscillator per user table
    # Outer Periphery values
    out_periph = {'M': 0.20, 'N': 0.15, 'L': 0.10}[settings['densityLevel']]
    # Inner Periphery values (all zero per table)
    in_periph = {'M': 0.00, 'N': 0.00, 'L': 0.00}[settings['densityLevel']]
    
    params = _params(pattern, housing)
    print(f"DEBUG corner_concave: _params returned = {params}")
    print(f"DEBUG corner_concave: housing rowSpan = {housing.get('rowSpan')}")
    print(f"DEBUG corner_concave: housing columnSpan = {housing.get('columnSpan')}")
    
    # Round-off factor: round off to the nearest two place decimal
    pattern['sizeRoundoff'] = 0.01
    pad = {
        'width': params['Wmax'] + out_periph + in_periph,
        'height': params['Tmax'] + out_periph + in_periph,
        'distance2': housing['rowSpan']['nom'] + out_periph / 2 - in_periph / 2,
        'distance1': housing['columnSpan']['nom'] + out_periph / 2 - in_periph / 2,
        'courtyard': {'M': 0.40, 'N': 0.20, 'L': 0.10}[settings['densityLevel']],
    }
    print(f"DEBUG corner_concave: calculated pad = {pad}")
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad1 = (pad['distance1'] + pad['width'] - housing['rowSpan']['nom']) / 2
    lead_to_pad2 = (pad['distance2'] + pad['height'] - housing['columnSpan']['nom']) / 2
    if lead_to_pad1 < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad1
        pad['width'] += d
        pad['distance1'] += d
    if lead_to_pad2 < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad2
        pad['height'] += d
        pad['distance2'] += d
    return pad

def son(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    params = _nolead(pattern, housing)
    # IPC-7351 SON (Table 3-16): courtyard and 0.05 mm round-off
    params['courtyard'] = {'M': 0.40, 'N': 0.20, 'L': 0.10}[settings['densityLevel']]
    pattern['sizeRoundoff'] = 0.05
    params['Lmin'] = housing['bodyWidth']['min']
    params['Lmax'] = housing['bodyWidth']['max']
    if 'pullBack' in housing:
        params['Lmin'] -= 2 * housing['pullBack']['nom']
        params['Lmax'] -= 2 * housing['pullBack']['nom']
    
    print(f"DEBUG SON: Body Lmin={params['Lmin']:.3f}, Lmax={params['Lmax']:.3f}")
    print(f"DEBUG SON: Lead Tmin={params['Tmin']:.3f}, Tmax={params['Tmax']:.3f}")
    print(f"DEBUG SON: IPC params Jt={params['Jt']:.3f}, Jh={params['Jh']:.3f}, Js={params['Js']:.3f}")
    
    ipc = _ipc7351(params)
    print(f"DEBUG SON: IPC results Zmax={ipc['Zmax']:.3f}, Gmin={ipc['Gmin']:.3f}, Xmax={ipc['Xmax']:.3f}")
    
    # Calculate pad protrusion for verification
    pad_protrusion = (ipc['Zmax'] - params['Lmax']) / 2
    print(f"DEBUG SON: Pad protrusion from body edge = {pad_protrusion:.3f}mm (should be ~{params['Jt']:.3f}mm + tolerances)")
    
    ipc['clearance'] = settings['clearance']['padToPad']
    ipc['pitch'] = housing['pitch']
    pad = _pad(ipc, pattern)
    if 'leadLength1' in housing:
        dw = housing['leadLength1']['nom'] - housing['leadLength']['nom']
        space = pad['distance'] - pad['width']
        if (space - dw) < settings['clearance']['padToPad']:
            dw = space - settings['clearance']['padToPad']
        pad['width1'] = pad['width'] + dw
    pad['courtyard'] = params['courtyard']
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad = (pad['distance'] + pad['width'] - housing['bodyWidth']['nom']) / 2
    if lead_to_pad < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad
        pad['width'] += d
        pad['distance'] += d
    return pad


def quad(pattern: dict, housing: dict, option: str) -> dict:
    settings = pattern['settings']
    if option == 'qfn':
        params = _nolead(pattern, housing)
        # IPC-7351 QFN courtyard per user table - same as SON
        params['courtyard'] = {'M': 0.40, 'N': 0.20, 'L': 0.10}[settings['densityLevel']]
        pattern['sizeRoundoff'] = 0.05
        params['Lmin'] = housing['bodyWidth']['min']
        params['Lmax'] = housing['bodyWidth']['max']
        if 'pullBack' in housing:
            params['Lmin'] -= 2 * housing['pullBack']['nom']
            params['Lmax'] -= 2 * housing['pullBack']['nom']
        row_ipc = _ipc7351(params)
        params['Lmin'] = housing['bodyLength']['min']
        params['Lmax'] = housing['bodyLength']['max']
        if 'pullBack' in housing:
            params['Lmin'] -= 2 * housing['pullBack']['nom']
            params['Lmax'] -= 2 * housing['pullBack']['nom']
        column_ipc = _ipc7351(params)
        row_span = housing['bodyWidth']['nom']
        column_span = housing['bodyLength']['nom']
    elif option == 'qfp':
        params = _gullwing(pattern, housing)
        params['Lmin'] = housing['rowSpan']['min']
        params['Lmax'] = housing['rowSpan']['max']
        row_ipc = _ipc7351(params)
        params['Lmin'] = housing['columnSpan']['min']
        params['Lmax'] = housing['columnSpan']['max']
        column_ipc = _ipc7351(params)
        row_span = housing['rowSpan']['nom']
        column_span = housing['columnSpan']['nom']
    else:
        raise ValueError('Unsupported quad option')

    row_ipc['clearance'] = settings['clearance']['padToPad']
    row_ipc['pitch'] = housing['pitch']
    if option == 'qfp':
        row_ipc['body'] = housing['bodyWidth']['nom']
    row_pad = _pad(row_ipc, pattern)

    column_ipc['clearance'] = settings['clearance']['padToPad']
    column_ipc['pitch'] = housing['pitch']
    if option == 'qfp':
        column_ipc['body'] = housing['bodyLength']['nom']
    column_pad = _pad(column_ipc, pattern)

    pad = {
        'width1': row_pad['width'],
        'height1': row_pad['height'],
        'distance1': row_pad['distance'],
        'width2': column_pad['width'],
        'height2': column_pad['height'],
        'distance2': column_pad['distance'],
        'trimmed': row_pad['trimmed'] or column_pad['trimmed'],
        'courtyard': params['courtyard'],
    }
    pad = _choose_preferred(pad, pattern, housing)
    if pattern['settings'].get('preferManufacturer') and ('padWidth' in housing):
        if 'padSpace1' in housing:
            pad['distance1'] = housing['padSpace1'] + housing['padWidth']
        if 'padSpan1' in housing:
            pad['distance1'] = housing['padSpan1'] - housing['padWidth']
        if 'padSpace2' in housing:
            pad['distance2'] = housing['padSpace2'] + housing['padWidth']
        if 'padSpan2' in housing:
            pad['distance2'] = housing['padSpan2'] - housing['padWidth']

    lead_to_pad1 = (pad['distance1'] + pad['width1'] - row_span) / 2
    lead_to_pad2 = (pad['distance2'] + pad['width2'] - column_span) / 2
    if lead_to_pad1 < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad1
        pad['width1'] += d
        pad['distance1'] += d
        lead_to_pad1 = (pad['distance1'] + pad['width1'] - row_span) / 2
    if lead_to_pad2 < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad2
        pad['width2'] += d
        pad['distance2'] += d
    return pad

def pak(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    # Normalize lead width field for GUI (leadWidth used; map from leadWidth1 if provided)
    if 'leadWidth' not in housing and 'leadWidth1' in housing:
        housing['leadWidth'] = housing['leadWidth1']
    params = _gullwing(pattern, housing)
    params['Lmin'] = housing['leadSpan']['min']
    params['Lmax'] = housing['leadSpan']['max']
    lead_ipc = _ipc7351(params)
    lead_ipc['clearance'] = settings['clearance']['padToPad']
    lead_ipc['pitch'] = housing['pitch']
    lead_pad = _pad(lead_ipc, pattern)

    params['Tmin'] = housing.get('tabLength', housing['tabLength'])['min'] if isinstance(housing.get('tabLength'), dict) else housing.get('tabLength')
    params['Tmax'] = housing.get('tabLength', housing['tabLength'])['max'] if isinstance(housing.get('tabLength'), dict) else housing.get('tabLength')
    params['Wmin'] = housing.get('tabWidth', housing['tabWidth'])['min'] if isinstance(housing.get('tabWidth'), dict) else housing.get('tabWidth')
    params['Wmax'] = housing.get('tabWidth', housing['tabWidth'])['max'] if isinstance(housing.get('tabWidth'), dict) else housing.get('tabWidth')
    tab_ipc = _ipc7351(params)
    tab_pad = _pad(tab_ipc, pattern)

    pad = {
        'width1': lead_pad['width'],
        'height1': lead_pad['height'],
        'distance1': lead_pad['distance'],
        'width2': tab_pad['width'],
        'height2': tab_pad['height'],
        'distance2': tab_pad['distance'],
        'courtyard': params['courtyard'],
    }
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad1 = (pad['distance1'] + pad['width1'] - housing['leadSpan']['nom']) / 2
    lead_to_pad2 = (pad['distance2'] + pad['width2'] - housing['leadSpan']['nom']) / 2
    if lead_to_pad1 < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad1
        pad['width1'] += d
        pad['distance1'] += d
    if lead_to_pad2 < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad2
        pad['width2'] += d
        pad['distance2'] += d
    return pad


def two_pin(pattern: dict, housing: dict, option: str = 'chip') -> dict:
    settings = pattern['settings']
    
    def _get_height(h: dict) -> float:
        hv = h.get('height')
        if isinstance(hv, dict):
            if 'max' in hv:
                return hv['max']
            if 'nom' in hv:
                return hv['nom']
            if 'min' in hv:
                return hv['min']
        if isinstance(hv, (int, float)):
            return hv
        return 0.0
    if option != 'radial':
        # For cylindrical parts (e.g., MELF), allow providing only bodyDiameter and bodyLength.nom
        # Do NOT prefill leadWidth/leadSpan here to avoid masking normalization below.
        if 'bodyWidth' not in housing and 'bodyDiameter' in housing:
            housing['bodyWidth'] = housing['bodyDiameter']

    if option == 'chip':
        # IPC-7351 Tables 3-5 and 3-6 for rectangular/square-end chips
        # Updated with length-based ranges per provided table
        bw = housing.get('bodyWidth')
        bl = housing.get('bodyLength')
        bw_nom = bw.get('nom', bw.get('max', bw.get('min', 0.0))) if isinstance(bw, dict) else float(bw or 0.0)
        bl_nom = bl.get('nom', bl.get('max', bl.get('min', 0.0))) if isinstance(bl, dict) else float(bl or 0.0)
        
        # Determine size category based on component length
        if bl_nom > 4.75:  # 2010 & Greater
            toes = {'L': 0.40, 'N': 0.50, 'M': 0.60}
            heels = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
            pattern['sizeRoundoff'] = 0.05
        elif bl_nom > 3.85:  # 1812 & 1825 (Length > 3.85 and <= 4.75 mm)
            toes = {'L': 0.30, 'N': 0.40, 'M': 0.50}
            heels = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
            pattern['sizeRoundoff'] = 0.05
        elif bl_nom > 2.85:  # 1206, 1210 & 0612 (Length > 2.85 and <= 3.85 mm)
            toes = {'L': 0.25, 'N': 0.35, 'M': 0.45}
            heels = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
            pattern['sizeRoundoff'] = 0.05
        elif bl_nom > 1.30:  # 0603, 0705 & 0805 (Length > 1.30 and <= 2.85 mm)
            toes = {'L': 0.20, 'N': 0.30, 'M': 0.40}
            heels = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
            pattern['sizeRoundoff'] = 0.05
        elif bl_nom > 0.75:  # 0402, 0306 & 0502 (Length > 0.75 and <= 1.30 mm)
            toes = {'L': 0.15, 'N': 0.20, 'M': 0.25}
            heels = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            courtyard = {'L': 0.10, 'N': 0.15, 'M': 0.20}[settings['densityLevel']]
            pattern['sizeRoundoff'] = 0.02
        elif bl_nom > 0.50:  # 0201 (Length > 0.50 and <= 0.75 mm)
            toes = {'L': 0.08, 'N': 0.10, 'M': 0.12}
            heels = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            courtyard = {'L': 0.10, 'N': 0.15, 'M': 0.20}[settings['densityLevel']]
            pattern['sizeRoundoff'] = 0.02
        else:  # 01005 & Less (Length <= 0.50 mm)
            toes = {'L': 0.04, 'N': 0.05, 'M': 0.06}
            heels = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.00}
            courtyard = {'L': 0.10, 'N': 0.15, 'M': 0.20}[settings['densityLevel']]
            pattern['sizeRoundoff'] = 0.02
    elif option == 'concave':
        toes = {'M': 0.55, 'N': 0.45, 'L': 0.35}
        heels = {'M': -0.05, 'N': -0.07, 'L': -0.1}
        sides = {'M': -0.05, 'N': -0.07, 'L': -0.1}
        courtyard = None
    elif option == 'crystal':
        height = _get_height(housing)
        if height > 10:
            # Height > 10mm
            toes = {'M': 1.0, 'N': 0.7, 'L': 0.4}
            heels = {'M': 0.1, 'N': 0.0, 'L': 0.0}
            sides = {'M': 0.6, 'N': 0.5, 'L': 0.4}
            courtyard = {'M': 0.8, 'N': 0.4, 'L': 0.2}[settings['densityLevel']]
        else:
            # Height <= 10mm
            toes = {'M': 0.7, 'N': 0.5, 'L': 0.3}
            heels = {'M': 0.05, 'N': 0.0, 'L': 0.0}
            sides = {'M': 0.5, 'N': 0.4, 'L': 0.3}
            courtyard = {'M': 0.4, 'N': 0.2, 'L': 0.1}[settings['densityLevel']]
        # Round-off per IPC Table 3-20
        pattern['sizeRoundoff'] = 0.05
    elif option == 'dfn':
        toes = {'M': 0.6, 'N': 0.4, 'L': 0.2}
        heels = {'M': 0.2, 'N': 0.1, 'L': 0.02}
        sides = {'M': 0.1, 'N': 0.05, 'L': 0.01}
        courtyard = None
    elif option == 'melf':
        # IPC-7351 MELF (RESMELF/DIOMELF) per table
        toes = {'M': 0.60, 'N': 0.40, 'L': 0.20}
        heels = {'M': 0.20, 'N': 0.10, 'L': 0.02}
        sides = {'M': 0.10, 'N': 0.05, 'L': 0.01}
        courtyard = {'M': 0.50, 'N': 0.25, 'L': 0.10}[settings['densityLevel']]
        # Round to 0.05 mm per table note
        pattern['sizeRoundoff'] = 0.05
    elif option == 'molded':
        # IPC-7351 height-based values for molded components
        height = housing.get('height', {}).get('max', 0)
        dl = settings['densityLevel']
        
        # Height-based toe/heel/side/courtyard values
        if height > 4.20:
            toes = {'L': 0.15, 'N': 0.20, 'M': 0.25}
            heels = {'L': 0.50, 'N': 0.60, 'M': 0.70}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[dl]
        elif height > 3.20:
            toes = {'L': 0.10, 'N': 0.15, 'M': 0.20}
            heels = {'L': 0.45, 'N': 0.55, 'M': 0.65}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[dl]
        elif height > 2.20:
            toes = {'L': 0.05, 'N': 0.10, 'M': 0.15}
            heels = {'L': 0.40, 'N': 0.50, 'M': 0.60}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[dl]
        elif height > 1.20:
            toes = {'L': 0.00, 'N': 0.05, 'M': 0.10}
            heels = {'L': 0.35, 'N': 0.45, 'M': 0.55}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[dl]
        else:  # height <= 1.20
            toes = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            heels = {'L': 0.30, 'N': 0.40, 'M': 0.50}
            sides = {'L': 0.00, 'N': 0.00, 'M': 0.05}
            courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[dl]
        
        pattern['sizeRoundoff'] = 0.05
    elif option == 'radial':
        pad = through_hole(pattern, housing)
        pad['distance'] = housing['leadSpan']['nom']
        pad['courtyard'] = {'M': 0.5, 'N': 0.25, 'L': 0.12}[settings['densityLevel']]
        return pad
    elif option == 'sod':
        toes = {'M': 0.55, 'N': 0.35, 'L': 0.15}
        heels = {'M': 0.45, 'N': 0.35, 'L': 0.25}
        sides = {'M': 0.05, 'N': 0.03, 'L': 0.01}
        courtyard = None
    elif option == 'sodfl':
        toes = {'M': 0.3, 'N': 0.2, 'L': 0.1}
        heels = {'M': 0.0, 'N': 0.0, 'L': 0.0}
        sides = {'M': 0.05, 'N': 0.0, 'L': 0.0}
        courtyard = {'M': 0.4, 'N': 0.2, 'L': 0.1}[settings['densityLevel']]
    else:
        raise ValueError('Unsupported two-pin option')

    dl = settings['densityLevel']
    toe = _density_value(toes, dl)
    heel = _density_value(heels, dl)
    side = _density_value(sides, dl)

    # For two-pin families, CoffeeScript normalizes min/nom/max here
    # leadSpan defaults to bodyLength; leadWidth defaults to bodyWidth
    if 'leadSpan' not in housing:
        bl = housing.get('bodyLength')
        if isinstance(bl, dict) and 'nom' in bl:
            housing['leadSpan'] = {
                'min': bl.get('min', bl['nom']),
                'nom': bl['nom'],
                'max': bl.get('max', bl['nom']),
            }
        elif isinstance(bl, (int, float)):
            housing['leadSpan'] = {'min': bl, 'nom': bl, 'max': bl}
    if 'leadWidth' not in housing:
        bw = housing.get('bodyWidth')
        if isinstance(bw, dict):
            nom = bw.get('nom', bw.get('max', bw.get('min')))
            mn = bw.get('min', nom)
            mx = bw.get('max', nom)
            housing['leadWidth'] = {'min': mn, 'max': mx}
        elif isinstance(bw, (int, float)):
            housing['leadWidth'] = {'min': bw, 'max': bw}

    params = _params(pattern, housing)
    # Allow overrides on the pattern, else use density-driven defaults
    params['Jt'] = pattern.get('toe', toe)
    params['Jh'] = pattern.get('heel', heel)
    params['Js'] = pattern.get('side', side)
    params['Lmin'] = housing['leadSpan']['min']
    params['Lmax'] = housing['leadSpan']['max']
    
    # Debug output for CAE components
    if option == 'crystal':
        print(f"=== CAE DEBUG ===")
        print(f"leadSpan: {housing.get('leadSpan')}")
        print(f"leadLength: {housing.get('leadLength')}")
        print(f"leadWidth: {housing.get('leadWidth')}")
        print(f"height: {housing.get('height')}")
        print(f"densityLevel: {settings['densityLevel']}")
        print(f"toe/heel/side: {toe}/{heel}/{side}")
        print(f"params: {params}")
    
    ipc = _ipc7351(params)
    
    if option == 'crystal':
        print(f"ipc: {ipc}")
    ipc['clearance'] = settings['clearance']['padToPad']
    pad = _pad(ipc, pattern)
    pad['courtyard'] = courtyard if 'courtyard' in locals() and courtyard is not None else params['courtyard']
    pad = _choose_preferred(pad, pattern, housing)
    
    if option == 'crystal':
        print(f"final pad: {pad}")
    lead_to_pad = (pad['distance'] + pad['width'] - housing['leadSpan']['nom']) / 2
    if lead_to_pad < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad
        pad['width'] += d
        pad['distance'] += d
    return pad


def pad_diameter(pattern: dict, housing: dict, hole_diameter: float) -> float:
    settings = pattern['settings']
    pad_d = hole_diameter * settings['ratio']['padToHole']
    if pad_d < (hole_diameter + 2 * settings['minimum']['ringWidth']):
        pad_d = hole_diameter + 2 * settings['minimum']['ringWidth']
    if ('pitch' in housing) or ('horizontalPitch' in housing and 'verticalPitch' in housing):
        pitch = housing['pitch'] if 'pitch' in housing else min(abs(housing['horizontalPitch']), abs(housing['verticalPitch']))
        clearance = housing.get('padSpace', settings['clearance']['padToPad'])
        if pad_d > pitch - clearance:
            pad_d = pitch - clearance
    size_roundoff = pattern.get('sizeRoundoff', 0.05)
    return round(pad_d / size_roundoff) * size_roundoff


def through_hole(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    if 'leadDiameter' in housing:
        ld = housing['leadDiameter']
        diameter = ld['max'] if isinstance(ld, dict) else ld
    else:
        lw = housing.get('leadWidth')
        lh = housing.get('leadHeight')
        w = lw['max'] if isinstance(lw, dict) else float(lw or 0)
        h = lh['max'] if isinstance(lh, dict) else float(lh or 0)
        diameter = (w * w + h * h) ** 0.5
    hole = diameter + 2 * settings['clearance']['leadToHole']
    if hole < settings['minimum']['holeDiameter']:
        hole = settings['minimum']['holeDiameter']
    size_roundoff = pattern.get('sizeRoundoff', 0.05)
    hole = _ceil_to(hole, size_roundoff)
    pad_d = pad_diameter(pattern, housing, hole)
    return {'hole': hole, 'width': pad_d, 'height': pad_d}


def _sot_gullwing(pattern: dict, housing: dict) -> dict:
    """SOT-specific gullwing parameters based on pitch ranges"""
    settings = pattern['settings']
    pitch = housing['pitch']
    
    # IPC-7351 SOT packages: pitch-based toe/heel/side/courtyard per user table
    if pitch > 1.92:
        # Pitch > 1.92 mm
        toes = {'L': 0.20, 'N': 0.25, 'M': 0.30}
        heels = {'L': 0.30, 'N': 0.35, 'M': 0.40}
        sides = {'L': 0.05, 'N': 0.06, 'M': 0.07}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.95:
        # Pitch > 0.95 and <= 1.92 mm
        toes = {'L': 0.15, 'N': 0.20, 'M': 0.25}
        heels = {'L': 0.20, 'N': 0.25, 'M': 0.30}
        sides = {'L': 0.04, 'N': 0.05, 'M': 0.06}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.65:
        # Pitch > 0.65 and <= 0.95 mm
        toes = {'L': 0.15, 'N': 0.20, 'M': 0.25}
        heels = {'L': 0.20, 'N': 0.25, 'M': 0.30}
        sides = {'L': 0.03, 'N': 0.04, 'M': 0.05}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.50:
        # Pitch > 0.50 and <= 0.65 mm
        toes = {'L': 0.10, 'N': 0.15, 'M': 0.20}
        heels = {'L': 0.15, 'N': 0.20, 'M': 0.25}
        sides = {'L': 0.01, 'N': 0.02, 'M': 0.03}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    elif pitch > 0.40:
        # Pitch > 0.40 and <= 0.50 mm
        toes = {'L': 0.10, 'N': 0.15, 'M': 0.20}
        heels = {'L': 0.15, 'N': 0.20, 'M': 0.25}
        sides = {'L': 0.00, 'N': 0.00, 'M': 0.00}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    else:
        # Pitch <= 0.40 mm
        toes = {'L': 0.10, 'N': 0.15, 'M': 0.20}
        heels = {'L': 0.15, 'N': 0.20, 'M': 0.25}
        sides = {'L': 0.00, 'N': 0.00, 'M': 0.00}
        courtyard = {'L': 0.10, 'N': 0.20, 'M': 0.40}[settings['densityLevel']]
    
    params = _params(pattern, housing)
    params['Jt'] = pattern.get('toe', _density_value(toes, settings['densityLevel']))
    params['Jh'] = pattern.get('heel', _density_value(heels, settings['densityLevel']))
    params['Js'] = pattern.get('side', _density_value(sides, settings['densityLevel']))
    params['courtyard'] = courtyard
    # Round to 0.05 mm grid for pad sizes per table note
    pattern['sizeRoundoff'] = 0.05
    return params


def sot(pattern: dict, housing: dict) -> dict:
    settings = pattern['settings']
    # adapt leadWidth to leadWidth1 like CoffeeScript
    housing['leadWidth'] = housing['leadWidth1']
    params = _flatlead(pattern, housing) if housing.get('flatlead') else _sot_gullwing(pattern, housing)
    params['Lmin'] = housing['leadSpan']['min']
    params['Lmax'] = housing['leadSpan']['max']
    params['body'] = housing['bodyWidth']
    ipc1 = _ipc7351(params)
    ipc1['clearance'] = settings['clearance']['padToPad']
    ipc1['pitch'] = housing['pitch']
    ipc1['body'] = housing['bodyWidth']['nom']
    pad1 = _pad(ipc1, pattern)

    params['Wmin'] = housing['leadWidth2']['min']
    params['Wmax'] = housing['leadWidth2']['max']
    ipc2 = _ipc7351(params)
    # ipc2['body'] = housing['bodyWidth']['nom']  # Removed to prevent body constraint trimming
    pad2 = _pad(ipc2, pattern)

    pad = {
        'width1': pad1['width'],
        'height1': pad1['height'],
        'distance': pad1['distance'],
        'width2': pad2['width'],
        'height2': pad2['height'],
        'courtyard': params['courtyard'],
        'trimmed': pad1['trimmed'] or pad2['trimmed'],
    }
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad = (pad['distance'] + pad['width1'] / 2 + pad['width2'] / 2 - housing['leadSpan']['nom']) / 2
    if lead_to_pad < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad
        pad['width1'] += d
        pad['width2'] += d
        pad['distance'] += d
    return pad


def sotfl(pattern: dict, housing: dict) -> dict:
    """SOTFL calculator using custom flatlead parameters without thermal pad"""
    settings = pattern['settings']
    # Ensure leadWidth1 and leadWidth2 are set for sot() function
    if 'leadWidth1' not in housing:
        housing['leadWidth1'] = housing['leadWidth']
    if 'leadWidth2' not in housing:
        housing['leadWidth2'] = housing['leadWidth']
    
    # Use custom SOTFL flatlead parameters
    params = _sotfl_flatlead(pattern, housing)
    params['Lmin'] = housing['leadSpan']['min']
    params['Lmax'] = housing['leadSpan']['max']
    params['body'] = housing['bodyWidth']
    ipc1 = _ipc7351(params)
    ipc1['clearance'] = settings['clearance']['padToPad']
    ipc1['pitch'] = housing['pitch']
    # ipc1['body'] = housing['bodyWidth']['nom']  # Removed to prevent body constraint trimming
    pad1 = _pad(ipc1, pattern)

    params['Wmin'] = housing['leadWidth2']['min']
    params['Wmax'] = housing['leadWidth2']['max']
    ipc2 = _ipc7351(params)
    # ipc2['body'] = housing['bodyWidth']['nom']  # Removed to prevent body constraint trimming
    pad2 = _pad(ipc2, pattern)

    pad = {
        'width1': pad1['width'],
        'height1': pad1['height'],
        'distance': pad1['distance'],
        'width2': pad2['width'],
        'height2': pad2['height'],
        'courtyard': params['courtyard'],
        'trimmed': pad1['trimmed'] or pad2['trimmed'],
    }
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad = (pad['distance'] + pad['width1'] / 2 + pad['width2'] / 2 - housing['leadSpan']['nom']) / 2
    if lead_to_pad < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad
        pad['width1'] += d
        pad['width2'] += d
        pad['distance'] += d
    return pad


def soj(pattern: dict, housing: dict) -> dict:
    """SOJ calculator using custom J-lead parameters"""
    settings = pattern['settings']
    # Use custom SOJ J-lead parameters
    params = _soj_jlead(pattern, housing)
    params['Lmin'] = housing['leadSpan']['min']
    params['Lmax'] = housing['leadSpan']['max']
    ipc = _ipc7351(params)
    ipc['clearance'] = settings['clearance']['padToPad']
    ipc['pitch'] = housing['pitch']
    pad = _pad(ipc, pattern)
    pad['courtyard'] = params['courtyard']
    pad = _choose_preferred(pad, pattern, housing)
    lead_to_pad = (pad['distance'] + pad['width'] - housing['leadSpan']['nom']) / 2
    if lead_to_pad < settings['minimum']['spaceForIron']:
        d = settings['minimum']['spaceForIron'] - lead_to_pad
        pad['width'] += d
        pad['distance'] += d
    return pad

