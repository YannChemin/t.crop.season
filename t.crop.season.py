#!/usr/bin/env python3
# %Module
# % description: Derives crop development stage and irrigation status from Sentinel-1/Sentinel-2 time series (STRDS) over a period of interest.
# % keyword: imagery
# % keyword: temporal
# % keyword: satellite
# % keyword: Sentinel
# % keyword: Sentinel-1
# % keyword: Sentinel-2
# % keyword: crop
# % keyword: phenology
# % keyword: irrigation
# % keyword: agriculture
# %end

# %option G_OPT_STRDS_INPUT
# % key: red
# % description: STRDS of Sentinel-2 red reflectance (e.g. B04)
# %end

# %option G_OPT_STRDS_INPUT
# % key: nir
# % description: STRDS of Sentinel-2 NIR reflectance (e.g. B08)
# %end

# %option G_OPT_STRDS_INPUT
# % key: swir
# % description: STRDS of Sentinel-2 SWIR reflectance (e.g. B11), used for NDWI
# %end

# %option G_OPT_STRDS_INPUT
# % key: vv
# % description: STRDS of Sentinel-1 VV backscatter (dB)
# %end

# %option G_OPT_STRDS_INPUT
# % key: vh
# % description: STRDS of Sentinel-1 VH backscatter (dB)
# %end

# %option G_OPT_STRDS_INPUT
# % key: precip
# % required: no
# % description: Optional STRDS of precipitation (e.g. from t.in.era5), used to separate rain from irrigation
# %end

# %option
# % key: start
# % type: string
# % required: yes
# % description: Start date of period of interest (YYYY-MM-DD)
# %end

# %option
# % key: end
# % type: string
# % required: yes
# % description: End date of period of interest (YYYY-MM-DD)
# %end

# %option G_OPT_R_OUTPUT
# % key: output
# % description: Prefix for output raster maps and STRDS
# %end

# %option
# % key: theta
# % type: double
# % required: no
# % answer: 31.0
# % description: Sentinel-1 incidence angle in degrees, used by the Water Cloud Model
# %end

# %option
# % key: wcm_a
# % type: double
# % required: no
# % answer: 0.0012
# % description: Water Cloud Model vegetation coefficient A (Bindlish & Barros)
# %end

# %option
# % key: wcm_b
# % type: double
# % required: no
# % answer: 0.091
# % description: Water Cloud Model vegetation coefficient B (Bindlish & Barros)
# %end

# %option
# % key: anomaly_threshold
# % type: double
# % required: no
# % answer: 1.5
# % description: Soil backscatter anomaly threshold (dB above dry baseline) to flag a wetting event
# %end

# %option
# % key: rain_threshold
# % type: double
# % required: no
# % answer: 2.0
# % description: Precipitation threshold (mm, summed over the 3 days before a SAR date) below which a wetting event is attributed to irrigation rather than rain
# %end

# %option
# % key: sos_fraction
# % type: double
# % required: no
# % answer: 0.5
# % description: Fraction of seasonal amplitude used to define start/end of season crossings
# %end

# %option
# % key: baseline_percentile
# % type: double
# % required: no
# % answer: 5.0
# % description: Percentile of the NDVI time series used as the season baseline (background/bare-soil level)
# %end

# %option
# % key: peak_percentile
# % type: double
# % required: no
# % answer: 95.0
# % description: Percentile of the NDVI time series used as the season peak level
# %end

# %option
# % key: min_amplitude
# % type: double
# % required: no
# % answer: 0.1
# % description: Minimum NDVI amplitude (peak_percentile - baseline_percentile, over the whole period) for a pixel to be considered to have any detectable crop cycle at all, used by multi-cycle detection (-m)
# %end

# %option
# % key: min_cycle_days
# % type: double
# % required: no
# % answer: 60
# % description: Minimum SOS-to-EOS duration (days) for a detected cycle to be kept (rejects noise-driven blips); raise for perennial crops (e.g. 270 for sugarcane)
# %end

# %option
# % key: max_gap_days
# % type: double
# % required: no
# % answer: 45
# % description: Below-threshold gaps shorter than this (days) are merged into the surrounding cycle instead of ending it - needed so a brief cloud-noise dip or a perennial crop's inter-ratoon canopy dip doesn't fragment one real cycle into several; raise for perennial crops (e.g. 90-120 for sugarcane)
# %end

# %option
# % key: smooth_window
# % type: integer
# % required: no
# % answer: 3
# % description: Rolling-median smoothing window (in samples) applied to each pixel's NDVI series before multi-cycle threshold-crossing detection (-m); 1 disables smoothing
# %end

# %option
# % key: max_cycles
# % type: integer
# % required: no
# % answer: 5
# % description: Maximum number of per-pixel cycles to keep/write with -m (a pixel with more detected cycles keeps only the most recent max_cycles)
# %end

# %option
# % key: sar_gap_days
# % type: double
# % required: no
# % answer: 10
# % description: With -m, a Sentinel-1 (cross-ratio) observation is only added to the crossing-detection series if no NDVI observation exists within this many days of it - lets SAR fill cloud gaps without displacing optical data where both are available
# %end

# %option
# % key: harvest_snap_days
# % type: double
# % required: no
# % answer: 20
# % description: With -m, each detected harvest (EOS) date is refined to the sharpest Sentinel-1 cross-ratio drop within this many days of the NDVI-based estimate (a ratoon cut's bare-soil exposure is a cleaner SAR signal than NDVI's gradual senescence); 0 disables snapping
# %end

# %option G_OPT_V_INPUT
# % key: training
# % required: no
# % description: Optional vector map of training points/polygons for Random Forest classification
# %end

# %option G_OPT_DB_COLUMN
# % key: training_column
# % required: no
# % description: Attribute column in the training vector holding class labels
# %end

# %flag
# % key: c
# % description: Train and apply a Random Forest classifier using the training vector (requires training= and training_column=)
# %end

# %flag
# % key: f
# % description: Fast mode - use amplitude-threshold phenology only, skip the per-pixel double-tanh curve fit
# %end

# %flag
# % key: m
# % description: Multi-cycle mode - detect ALL per-pixel planting(SOS)/harvest(EOS) cycles over the period (not just one whole-record fit), fusing Sentinel-2 NDVI (primary) with Sentinel-1 cross-ratio (cloud-gap-fill + harvest-date snapping) and with noise-merging and a minimum cycle length, suitable for annual crops with several cycles in the record AND for perennial/ratoon crops (e.g. sugarcane) with one long cycle. Writes <output>_cycleN_sos/_eos, <output>_ncycles, <output>_last_sos/_last_eos/_last_still_growing (the last-cycle triplet t.crop.yield's season_sos=/season_eos=/season_still_growing= options expect).
# %end

# %rules
# % requires: -c, training
# % requires: -c, training_column
# %end

import sys
from datetime import datetime, timedelta

import grass.script as gs


# ---------------------------------------------------------------------------
# Development-stage class codes, shared between the classification logic and
# the r.category labels written onto the output STRDS.
# ---------------------------------------------------------------------------
STAGE_LABELS = {
    0: "bare / pre-emergence",
    1: "emergence / early vegetative",
    2: "vegetative",
    3: "reproductive / peak",
    4: "senescence",
    5: "post-harvest / bare",
}

STAGE_CATEGORY_RULES = "\n".join(f"{k}|{v}" for k, v in STAGE_LABELS.items()) + "\n"


def strds_maps(strds_name, start, end):
    """Return a sorted list of (map_name, datetime) registered in strds_name
    within [start, end] (inclusive), using t.rast.list."""
    where = f"start_time >= '{start}' and start_time <= '{end} 23:59:59'"
    out = gs.read_command(
        "t.rast.list",
        input=strds_name,
        columns="name,start_time",
        where=where,
        separator="|",
        quiet=True,
    )
    maps = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("name|"):
            continue
        name, start_time = line.split("|", 1)
        # t.rast.list start_time format: "YYYY-MM-DD HH:MM:SS[.ffffff]"
        start_time = start_time.split(".")[0]
        dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        maps.append((name, dt))
    maps.sort(key=lambda m: m[1])
    return maps


def days_since(dates, ref):
    """Convert a list of datetime objects to a numpy array of float days since ref."""
    import numpy as np

    return np.array([(d - ref).total_seconds() / 86400.0 for d in dates])


def read_stack(map_names):
    """Read a list of raster map names into a 3D numpy array (time, row, col)."""
    import numpy as np
    from grass.script import array as garray

    arrays = []
    for name in map_names:
        a = garray.array(mapname=name)
        arrays.append(np.array(a, dtype=np.float64))
    return np.stack(arrays, axis=0)


def write_raster(arr, mapname, nodata_value=None, categorical=False):
    """Write a 2D numpy array as a GRASS raster map.

    categorical=True writes a CELL (integer) map, needed for outputs that
    get r.category/r.colors treatments requiring a discrete raster (e.g.
    color=random, which r.colors refuses on floating-point maps).
    """
    import numpy as np
    from grass.script import array as garray

    dtype = np.int32 if categorical else np.float64
    out = garray.array(dtype=dtype)
    if categorical:
        arr = np.where(np.isfinite(arr), arr, -1)
    elif nodata_value is not None:
        arr = np.where(np.isfinite(arr), arr, nodata_value)
    out[...] = arr
    out.write(mapname=mapname, overwrite=True, null=-1 if categorical else None)


def double_tanh(t, a0, a1, a2, a3, a4, a5, a6):
    """Meroni et al. (2021) double hyperbolic tangent phenology model."""
    import numpy as np

    green_up = a1 * (np.tanh((t - a2) * a3) + 1.0) / 2.0
    decay = a4 * (np.tanh((t - a5) * a6) + 1.0) / 2.0 - a4
    return a0 + green_up + decay


def fit_pixel_phenology(t, y, baseline_pct, peak_pct, sos_fraction):
    """Fit the double-tanh model to one pixel's NDVI time series.

    Returns a dict with sos, pos, eos, amplitude, baseline, or None if the
    pixel cannot be characterised (too few valid observations, or the fit
    does not converge and the amplitude fallback also fails).
    """
    import numpy as np
    from scipy.optimize import curve_fit

    valid = np.isfinite(y)
    if valid.sum() < 8:
        return None

    tv = t[valid]
    yv = y[valid]

    baseline = np.percentile(yv, baseline_pct)
    peak = np.percentile(yv, peak_pct)
    amplitude = peak - baseline
    if amplitude < 0.1:
        return None

    # Amplitude-threshold estimate (Meroni et al. "SOS50/EOS50"), used both as
    # the initial guess for the curve fit and as the fallback when the fit
    # itself does not converge.
    threshold = baseline + sos_fraction * amplitude
    peak_idx = np.argmax(yv)
    rising = np.where((yv[:peak_idx] < threshold))[0]
    sos_fallback = tv[rising[-1] + 1] if len(rising) and rising[-1] + 1 < peak_idx else tv[0]
    falling = np.where((yv[peak_idx:] < threshold))[0]
    eos_fallback = tv[peak_idx + falling[0]] if len(falling) else tv[-1]
    pos_fallback = tv[peak_idx]

    fallback = {
        "sos": float(sos_fallback),
        "pos": float(pos_fallback),
        "eos": float(eos_fallback),
        "amplitude": float(amplitude),
        "baseline": float(baseline),
    }

    if valid.sum() < 3 + 3:
        # Not enough points to trust a 7-parameter fit; keep the fallback.
        return fallback

    p0 = [
        baseline,
        amplitude,
        sos_fallback,
        0.15,
        amplitude,
        eos_fallback,
        0.15,
    ]
    try:
        popt, _ = curve_fit(double_tanh, tv, yv, p0=p0, maxfev=2000)
        a0, a1, a2, a3, a4, a5, a6 = popt
        fit_amplitude = a1
        if fit_amplitude < 0.05 or a2 >= a5:
            return fallback
        fit_t = np.linspace(tv[0], tv[-1], 400)
        fit_y = double_tanh(fit_t, *popt)
        fit_peak_idx = np.argmax(fit_y)
        threshold_fit = a0 + sos_fraction * a1
        rising = np.where(fit_y[:fit_peak_idx] < threshold_fit)[0]
        sos = fit_t[rising[-1] + 1] if len(rising) and rising[-1] + 1 < fit_peak_idx else fit_t[0]
        falling = np.where(fit_y[fit_peak_idx:] < threshold_fit)[0]
        eos = fit_t[fit_peak_idx + falling[0]] if len(falling) else fit_t[-1]
        return {
            "sos": float(sos),
            "pos": float(fit_t[fit_peak_idx]),
            "eos": float(eos),
            "amplitude": float(fit_amplitude),
            "baseline": float(a0),
        }
    except (RuntimeError, ValueError):
        return fallback


def compute_phenology(ndvi_stack, t_days, baseline_pct, peak_pct, sos_fraction, fast):
    """Compute SOS/POS/EOS/amplitude/baseline rasters (2D) from an NDVI stack.

    fast=True skips the per-pixel curve fit and uses the vectorised
    amplitude-threshold method everywhere (much faster, slightly noisier).
    """
    import numpy as np

    n_time, n_rows, n_cols = ndvi_stack.shape
    sos = np.full((n_rows, n_cols), np.nan)
    pos = np.full((n_rows, n_cols), np.nan)
    eos = np.full((n_rows, n_cols), np.nan)
    amplitude = np.full((n_rows, n_cols), np.nan)
    baseline = np.full((n_rows, n_cols), np.nan)

    if fast:
        baseline_arr = np.nanpercentile(ndvi_stack, baseline_pct, axis=0)
        peak_arr = np.nanpercentile(ndvi_stack, peak_pct, axis=0)
        amp_arr = peak_arr - baseline_arr
        threshold = baseline_arr + sos_fraction * amp_arr
        peak_idx = np.nanargmax(ndvi_stack, axis=0)

        for r in range(n_rows):
            for c in range(n_cols):
                if not np.isfinite(amp_arr[r, c]) or amp_arr[r, c] < 0.1:
                    continue
                series = ndvi_stack[:, r, c]
                pidx = peak_idx[r, c]
                th = threshold[r, c]
                rising = np.where(series[:pidx] < th)[0]
                sos_i = rising[-1] + 1 if len(rising) and rising[-1] + 1 < pidx else 0
                falling = np.where(series[pidx:] < th)[0]
                eos_i = pidx + falling[0] if len(falling) else n_time - 1
                sos[r, c] = t_days[sos_i]
                pos[r, c] = t_days[pidx]
                eos[r, c] = t_days[eos_i]
                amplitude[r, c] = amp_arr[r, c]
                baseline[r, c] = baseline_arr[r, c]
        return sos, pos, eos, amplitude, baseline

    gs.message("Fitting double hyperbolic tangent phenology model per pixel ...")
    total = n_rows * n_cols
    done = 0
    for r in range(n_rows):
        for c in range(n_cols):
            done += 1
            if done % max(1, total // 20) == 0:
                gs.percent(done, total, 5)
            series = ndvi_stack[:, r, c]
            result = fit_pixel_phenology(t_days, series, baseline_pct, peak_pct, sos_fraction)
            if result is None:
                continue
            sos[r, c] = result["sos"]
            pos[r, c] = result["pos"]
            eos[r, c] = result["eos"]
            amplitude[r, c] = result["amplitude"]
            baseline[r, c] = result["baseline"]
    gs.percent(1, 1, 1)
    return sos, pos, eos, amplitude, baseline


def smooth_series(y, window):
    """Rolling-median smoothing over consecutive valid samples (index-based,
    not date-gap aware - acceptable given the roughly regular cadence within
    one sensor's STRDS). window<=1 is a no-op."""
    import numpy as np

    if window <= 1:
        return y
    n = len(y)
    half = window // 2
    out = np.empty(n)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out[i] = np.median(y[lo:hi])
    return out


def normalize_to_reference(series, baseline_pct, peak_pct, ref_baseline, ref_amplitude):
    """Percentile-normalize `series` onto the same [ref_baseline,
    ref_baseline + ref_amplitude] scale as a reference series (here, one
    pixel's own NDVI baseline/amplitude), so a secondary signal (SAR cross-
    ratio) becomes directly comparable against the same sos_fraction
    threshold NDVI is tested against. Self-calibrating per pixel: only the
    *direction* of the relationship (more vegetation -> higher value) is
    assumed, not an absolute VV/VH-to-NDVI conversion."""
    import numpy as np

    valid = np.isfinite(series)
    if valid.sum() < 3:
        return np.full_like(series, np.nan)
    lo = np.percentile(series[valid], baseline_pct)
    hi = np.percentile(series[valid], peak_pct)
    spread = hi - lo
    if spread <= 0:
        return np.full_like(series, np.nan)
    frac = (series - lo) / spread
    return ref_baseline + frac * ref_amplitude


def snap_eos_to_sar(eos_day, sar_t, sar_y, window_days):
    """Refine one candidate EOS (harvest) date using the SAR cross-ratio.

    A harvest/ratoon cut is a discrete structural event - vegetation
    (volume-scattering) canopy is suddenly replaced by bare/stubble soil
    (surface/double-bounce scattering), which shows up as a sharp DROP in
    the cross-ratio (VH-VV, dB). That's a cleaner, higher-frequency signal
    for the exact harvest date than NDVI's gradual senescence decline, and
    SAR is cloud-independent so it's available even when optical isn't.
    Returns the date right after the steepest CR drop within
    [eos_day-window_days, eos_day+window_days], or the original eos_day
    unchanged if no SAR data / no actual drop is found in that window."""
    import numpy as np

    valid = np.isfinite(sar_y)
    if valid.sum() < 2:
        return eos_day
    tv, yv = sar_t[valid], sar_y[valid]
    order = np.argsort(tv)
    tv, yv = tv[order], yv[order]

    in_window = (tv >= eos_day - window_days) & (tv <= eos_day + window_days)
    idxs = np.where(in_window)[0]
    if len(idxs) < 2:
        return eos_day
    lo, hi = idxs[0], idxs[-1]
    diffs = np.diff(yv[lo:hi + 1])
    if len(diffs) == 0:
        return eos_day
    steepest = np.argmin(diffs)
    if diffs[steepest] >= 0:
        return eos_day  # no real drop in the window; keep the NDVI-based estimate
    return float(tv[lo + steepest + 1])


def detect_cycles(t, y, sos_fraction, baseline_pct, peak_pct, min_amplitude,
                   min_cycle_days, max_gap_days, smooth_window,
                   sar_t=None, sar_y=None, sar_gap_days=10, harvest_snap_days=20):
    """Detect all planting(SOS)->harvest(EOS) cycles in one pixel's NDVI
    time series (optionally fused with Sentinel-1), robust to short
    noise-driven dips.

    Unlike a single whole-record fit (compute_phenology/fit_pixel_phenology),
    this walks the (smoothed) series for every rising/falling threshold
    crossing, then MERGES cycles separated by a below-threshold gap shorter
    than max_gap_days before applying a min_cycle_days floor. That merge
    step is what makes this usable for perennial/ratoon crops: sugarcane's
    10-24 month cycle includes brief NDVI dips (cloud noise, partial
    regrowth after a ratoon cut) that would otherwise each read as a
    separate spurious 2-90 day "cycle" - exactly the failure mode observed
    feeding t.crop.yield's old single-cycle detector on real sugarcane data
    (detected durations topped out at 92 days, never approaching a year).

    If sar_t/sar_y (a per-pixel SAR cross-ratio series, e.g. VH-VV dB, on
    its own date axis) are given, Sentinel-1 is folded in two ways:
      1. GAP-FILL: SAR dates more than sar_gap_days from any NDVI
         observation are added to the crossing-detection series (percentile-
         normalized onto NDVI's own baseline/amplitude scale), so cloudy
         stretches - worst exactly when planting/early growth typically
         happens - still contribute crossing evidence instead of a blind
         spot.
      2. HARVEST SNAP: each detected EOS is refined to the nearest sharp SAR
         cross-ratio drop within harvest_snap_days (see snap_eos_to_sar) -
         SAR's discrete structural signal usually pinpoints a ratoon cut
         better than NDVI's gradual decline does.

    Returns a list of (sos_day, eos_day_or_None) tuples in chronological
    order; eos_day is None for a cycle still above threshold at the end of
    the series (still growing / not yet harvested).
    """
    import numpy as np

    valid = np.isfinite(y)
    if valid.sum() < 5:
        return []

    tv = t[valid]
    yv = smooth_series(y[valid], smooth_window)

    baseline = np.percentile(yv, baseline_pct)
    peak = np.percentile(yv, peak_pct)
    amplitude = peak - baseline
    if amplitude < min_amplitude:
        return []
    threshold = baseline + sos_fraction * amplitude

    tf, yf = list(tv), list(yv)
    if sar_t is not None and sar_y is not None:
        sar_norm = normalize_to_reference(sar_y, baseline_pct, peak_pct, baseline, amplitude)
        for i in range(len(sar_t)):
            if not np.isfinite(sar_norm[i]):
                continue
            if tv.size and np.min(np.abs(tv - sar_t[i])) <= sar_gap_days:
                continue  # NDVI already has coverage near this date
            tf.append(sar_t[i])
            yf.append(sar_norm[i])
    order = np.argsort(tf)
    tf = np.asarray(tf)[order]
    yf = np.asarray(yf)[order]

    above = yf > threshold

    raw = []
    sos_idx = None
    for i in range(len(above)):
        if above[i] and sos_idx is None:
            sos_idx = i
        elif not above[i] and sos_idx is not None:
            raw.append([sos_idx, i])
            sos_idx = None
    if sos_idx is not None:
        raw.append([sos_idx, None])
    if not raw:
        return []

    merged = [raw[0]]
    for sos_idx, eos_idx in raw[1:]:
        prev = merged[-1]
        if prev[1] is not None:
            gap_days = tf[sos_idx] - tf[prev[1]]
            if gap_days <= max_gap_days:
                prev[1] = eos_idx  # bridge the gap: extend the previous cycle
                continue
        merged.append([sos_idx, eos_idx])

    cycles = []
    for sos_idx, eos_idx in merged:
        sos_day = float(tf[sos_idx])
        eos_day = float(tf[eos_idx]) if eos_idx is not None else None
        if eos_day is not None and (eos_day - sos_day) < min_cycle_days:
            continue
        cycles.append((sos_day, eos_day))

    if sar_t is not None and sar_y is not None and cycles:
        cycles = [
            (sos_day, snap_eos_to_sar(eos_day, sar_t, sar_y, harvest_snap_days) if eos_day is not None else None)
            for sos_day, eos_day in cycles
        ]
    return cycles


def compute_cycles(ndvi_stack, t_days, baseline_pct, peak_pct, sos_fraction,
                    min_amplitude, min_cycle_days, max_gap_days, smooth_window,
                    max_cycles, cr_stack=None, sar_days=None,
                    sar_gap_days=10, harvest_snap_days=20):
    """Per-pixel multi-cycle detection over the whole raster stack.

    cr_stack/sar_days (Sentinel-1 cross-ratio (time,row,col) stack and its
    day-offset axis) are optional - when given, each pixel's SAR series is
    folded into detect_cycles for cloud-gap-filling and harvest-date
    snapping (see detect_cycles' docstring). Without them this is NDVI-only,
    same as before Sentinel-1 fusion was added.

    Returns (cycle_sos, cycle_eos) as (max_cycles, rows, cols) arrays (most
    recent max_cycles cycles kept, chronological order), ncycles (rows,cols)
    int count of ALL detected cycles (may exceed max_cycles), and
    last_sos/last_eos/last_still_growing (rows,cols) - the most recent
    cycle, which is what t.crop.yield's season_sos=/season_eos=/
    season_still_growing= options are meant to consume.
    """
    import numpy as np

    n_time, n_rows, n_cols = ndvi_stack.shape
    cycle_sos = np.full((max_cycles, n_rows, n_cols), np.nan)
    cycle_eos = np.full((max_cycles, n_rows, n_cols), np.nan)
    ncycles = np.zeros((n_rows, n_cols), dtype=np.int32)
    last_sos = np.full((n_rows, n_cols), np.nan)
    last_eos = np.full((n_rows, n_cols), np.nan)
    last_still_growing = np.zeros((n_rows, n_cols), dtype=np.int32)

    gs.message(
        "Detecting per-pixel crop cycles (multi-cycle mode"
        + (", Sentinel-1 fused)" if cr_stack is not None else ", NDVI-only - no SAR given)")
        + " ..."
    )
    total = n_rows * n_cols
    done = 0
    for r in range(n_rows):
        for c in range(n_cols):
            done += 1
            if done % max(1, total // 20) == 0:
                gs.percent(done, total, 5)
            cycles = detect_cycles(
                t_days, ndvi_stack[:, r, c], sos_fraction, baseline_pct, peak_pct,
                min_amplitude, min_cycle_days, max_gap_days, smooth_window,
                sar_t=sar_days, sar_y=cr_stack[:, r, c] if cr_stack is not None else None,
                sar_gap_days=sar_gap_days, harvest_snap_days=harvest_snap_days,
            )
            if not cycles:
                continue
            ncycles[r, c] = len(cycles)
            for i, (sos_d, eos_d) in enumerate(cycles[-max_cycles:]):
                cycle_sos[i, r, c] = sos_d
                if eos_d is not None:
                    cycle_eos[i, r, c] = eos_d
            last_sos_d, last_eos_d = cycles[-1]
            last_sos[r, c] = last_sos_d
            if last_eos_d is not None:
                last_eos[r, c] = last_eos_d
            else:
                last_still_growing[r, c] = 1
    gs.percent(1, 1, 1)
    return cycle_sos, cycle_eos, ncycles, last_sos, last_eos, last_still_growing


def classify_stage(date_days, sos, pos, eos):
    """Vectorised per-date development-stage classification (see STAGE_LABELS)."""
    import numpy as np

    stage = np.full(sos.shape, np.nan)
    valid = np.isfinite(sos) & np.isfinite(pos) & np.isfinite(eos)

    mid_veg = sos + (pos - sos) / 2.0
    peak_tol = np.maximum((eos - sos) * 0.1, 3.0)

    bare_pre = valid & (date_days < sos)
    early_veg = valid & (date_days >= sos) & (date_days < mid_veg)
    late_veg = valid & (date_days >= mid_veg) & (date_days < (pos - peak_tol))
    peak = valid & (date_days >= (pos - peak_tol)) & (date_days <= (pos + peak_tol))
    senescence = valid & (date_days > (pos + peak_tol)) & (date_days < eos)
    post_harvest = valid & (date_days >= eos)

    stage[bare_pre] = 0
    stage[early_veg] = 1
    stage[late_veg] = 2
    stage[peak] = 3
    stage[senescence] = 4
    stage[post_harvest] = 5
    return stage


def interp_to(target_days, source_days, source_stack):
    """Linearly interpolate a (time, row, col) stack from source_days onto
    target_days, per pixel, extrapolating with edge values."""
    import numpy as np

    n_rows, n_cols = source_stack.shape[1:]
    out = np.full((len(target_days), n_rows, n_cols), np.nan)
    for r in range(n_rows):
        for c in range(n_cols):
            series = source_stack[:, r, c]
            valid = np.isfinite(series)
            if valid.sum() < 2:
                continue
            out[:, r, c] = np.interp(target_days, source_days[valid], series[valid])
    return out


def compute_irrigation(
    vv_db,
    vh_db,
    ndvi_interp,
    theta_deg,
    wcm_a,
    wcm_b,
    anomaly_threshold,
    precip_recent,
    rain_threshold,
):
    """Water Cloud Model based soil backscatter anomaly and wetting-event flag.

    Returns dict of 3D (time,row,col) arrays: vv_anomaly_db, vh_anomaly_db,
    wetting_flag (0/1/2: none/irrigation/rain).
    """
    import numpy as np

    theta = np.radians(theta_deg)
    vwc = 0.098 * np.exp(4.225 * np.clip(ndvi_interp, -1.0, 1.0))
    tau2 = np.exp(-2.0 * wcm_b * vwc / np.cos(theta))

    results = {}
    for pol_name, sigma_db in (("vv", vv_db), ("vh", vh_db)):
        sigma_lin = 10.0 ** (sigma_db / 10.0)
        sigma_veg = wcm_a * vwc * np.cos(theta) * (1.0 - tau2)
        sigma_soil = (sigma_lin - sigma_veg) / np.where(tau2 == 0, np.nan, tau2)
        sigma_soil = np.where(sigma_soil > 0, sigma_soil, np.nan)
        dry_baseline = np.nanpercentile(sigma_soil, 10, axis=0)
        anomaly_db = 10.0 * np.log10(sigma_soil / dry_baseline)
        results[f"{pol_name}_anomaly_db"] = anomaly_db

    wetting = (results["vv_anomaly_db"] > anomaly_threshold).astype(np.float64)
    wetting[~np.isfinite(results["vv_anomaly_db"])] = np.nan

    flag = np.where(wetting == 1, 1.0, 0.0)  # default: irrigation
    if precip_recent is not None:
        rained = precip_recent > rain_threshold
        flag = np.where((wetting == 1) & rained, 2.0, flag)  # reclassify as rain
    flag[~np.isfinite(results["vv_anomaly_db"])] = np.nan
    results["wetting_flag"] = flag
    return results


def register_strds(strds_name, title, description, map_names, dates, ttype="strds"):
    gs.run_command(
        "t.create",
        type=ttype,
        temporaltype="absolute",
        output=strds_name,
        title=title,
        description=description,
        overwrite=True,
        quiet=True,
    )
    for name, dt in zip(map_names, dates):
        gs.run_command("r.timestamp", map=name, date=dt.strftime("%d %b %Y %H:%M:%S"), quiet=True)
    gs.run_command(
        "t.register",
        type="raster",
        input=strds_name,
        maps=",".join(map_names),
        overwrite=True,
        quiet=True,
    )


def main():
    import numpy as np

    options, flags = gs.parser()

    red_strds = options["red"]
    nir_strds = options["nir"]
    swir_strds = options["swir"]
    vv_strds = options["vv"]
    vh_strds = options["vh"]
    precip_strds = options["precip"] or None
    start = options["start"]
    end = options["end"]
    output = options["output"]
    theta_deg = float(options["theta"])
    wcm_a = float(options["wcm_a"])
    wcm_b = float(options["wcm_b"])
    anomaly_threshold = float(options["anomaly_threshold"])
    rain_threshold = float(options["rain_threshold"])
    sos_fraction = float(options["sos_fraction"])
    baseline_pct = float(options["baseline_percentile"])
    peak_pct = float(options["peak_percentile"])
    training = options["training"] or None
    training_column = options["training_column"] or None
    do_classify = flags["c"]
    fast_mode = flags["f"]
    multi_cycle_mode = flags["m"]
    min_amplitude = float(options["min_amplitude"])
    min_cycle_days = float(options["min_cycle_days"])
    max_gap_days = float(options["max_gap_days"])
    smooth_window = int(options["smooth_window"])
    max_cycles = int(options["max_cycles"])
    sar_gap_days = float(options["sar_gap_days"])
    harvest_snap_days = float(options["harvest_snap_days"])

    try:
        import grass.temporal as tgis

        tgis.init()
    except Exception as e:
        gs.fatal(f"Failed to initialise the temporal framework: {e}")

    # --- Gather optical (S2) and SAR (S1) date axes -----------------------
    gs.message("Reading STRDS registrations ...")
    red_maps = strds_maps(red_strds, start, end)
    nir_maps = strds_maps(nir_strds, start, end)
    swir_maps = strds_maps(swir_strds, start, end)
    vv_maps = strds_maps(vv_strds, start, end)
    vh_maps = strds_maps(vh_strds, start, end)

    if not red_maps or not nir_maps:
        gs.fatal("No red/NIR maps found in the given period; cannot compute NDVI.")
    if not vv_maps or not vh_maps:
        gs.fatal("No VV/VH maps found in the given period; cannot compute SAR features.")

    # Optical dates: intersection of red, nir, swir (same acquisition, i.e.
    # same calendar date already resampled onto one grid by r.in.sentinel).
    red_by_date = {d.date(): n for n, d in red_maps}
    nir_by_date = {d.date(): n for n, d in nir_maps}
    swir_by_date = {d.date(): n for n, d in swir_maps}
    optical_dates = sorted(set(red_by_date) & set(nir_by_date) & set(swir_by_date))
    if not optical_dates:
        gs.fatal("red/nir/swir STRDS have no common acquisition dates.")

    vv_by_date = {d.date(): n for n, d in vv_maps}
    vh_by_date = {d.date(): n for n, d in vh_maps}
    sar_dates = sorted(set(vv_by_date) & set(vh_by_date))
    if not sar_dates:
        gs.fatal("vv/vh STRDS have no common acquisition dates.")

    # Referenced to start= (not the first actually-observed date) so that
    # day-offsets are directly comparable with another module run against
    # the same start= - in particular t.crop.yield's season_sos=/
    # season_eos= consume this module's day-offset outputs and must agree
    # on what day 0 means.
    ref = datetime.strptime(start, "%Y-%m-%d")

    # --- NDVI / NDWI / CR per date -----------------------------------------
    gs.message(f"Computing NDVI/NDWI for {len(optical_dates)} date(s) ...")
    ndvi_maps, ndwi_maps = [], []
    ndvi_dt = []
    for d in optical_dates:
        red_m, nir_m, swir_m = red_by_date[d], nir_by_date[d], swir_by_date[d]
        ndvi_m = f"{output}_ndvi_{d.strftime('%Y%m%d')}"
        ndwi_m = f"{output}_ndwi_{d.strftime('%Y%m%d')}"
        gs.mapcalc(f"{ndvi_m} = float({nir_m} - {red_m}) / float({nir_m} + {red_m})", overwrite=True, quiet=True)
        gs.mapcalc(f"{ndwi_m} = float({nir_m} - {swir_m}) / float({nir_m} + {swir_m})", overwrite=True, quiet=True)
        ndvi_maps.append(ndvi_m)
        ndwi_maps.append(ndwi_m)
        ndvi_dt.append(datetime.combine(d, datetime.min.time()))

    gs.message(f"Computing SAR cross-ratio (VH-VV, dB) for {len(sar_dates)} date(s) ...")
    cr_maps = []
    sar_dt = []
    for d in sar_dates:
        vv_m, vh_m = vv_by_date[d], vh_by_date[d]
        cr_m = f"{output}_cr_{d.strftime('%Y%m%d')}"
        gs.mapcalc(f"{cr_m} = float({vh_m} - {vv_m})", overwrite=True, quiet=True)
        cr_maps.append(cr_m)
        sar_dt.append(datetime.combine(d, datetime.min.time()))

    register_strds(
        f"{output}_ndvi", "NDVI time series", "NDVI computed by t.crop.season", ndvi_maps, ndvi_dt
    )
    register_strds(
        f"{output}_ndwi", "NDWI time series", "NDWI computed by t.crop.season", ndwi_maps, ndvi_dt
    )
    register_strds(
        f"{output}_cr", "SAR cross-ratio (VH-VV, dB) time series",
        "SAR cross-ratio computed by t.crop.season", cr_maps, sar_dt,
    )

    # --- Phenology ----------------------------------------------------------
    gs.message("Reading NDVI raster stack ...")
    ndvi_stack = read_stack(ndvi_maps)
    t_days = days_since(ndvi_dt, ref)

    # Read the SAR stacks once, up front, so both multi-cycle detection (-m,
    # below) and the irrigation section (further down) share one read
    # instead of hitting disk twice for the same rasters.
    gs.message("Reading Sentinel-1 VV/VH raster stacks ...")
    vv_stack = read_stack([vv_by_date[d] for d in sar_dates])
    vh_stack = read_stack([vh_by_date[d] for d in sar_dates])
    sar_days = days_since(sar_dt, ref)
    cr_stack = vh_stack - vv_stack

    sos, pos, eos, amplitude, baseline = compute_phenology(
        ndvi_stack, t_days, baseline_pct, peak_pct, sos_fraction, fast_mode
    )

    for name, arr in (
        ("sos", sos),
        ("pos", pos),
        ("eos", eos),
        ("amplitude", amplitude),
        ("season_length", eos - sos),
    ):
        mapname = f"{output}_{name}"
        write_raster(arr, mapname)
        gs.run_command(
            "r.support", map=mapname,
            title=f"t.crop.season {name}",
            units="days since " + ref.strftime("%Y-%m-%d") if name != "amplitude" else "NDVI units",
            history=f"t.crop.season phenology output ({name})",
            quiet=True,
        )
    gs.message(f"Phenology rasters written: {output}_sos, {output}_pos, {output}_eos, "
               f"{output}_amplitude, {output}_season_length")

    # --- Multi-cycle detection (-m) ------------------------------------------
    if multi_cycle_mode:
        cycle_sos, cycle_eos, ncycles, last_sos, last_eos, last_still_growing = compute_cycles(
            ndvi_stack, t_days, baseline_pct, peak_pct, sos_fraction,
            min_amplitude, min_cycle_days, max_gap_days, smooth_window, max_cycles,
            cr_stack=cr_stack, sar_days=sar_days,
            sar_gap_days=sar_gap_days, harvest_snap_days=harvest_snap_days,
        )
        for i in range(max_cycles):
            n = i + 1
            write_raster(cycle_sos[i], f"{output}_cycle{n}_sos")
            write_raster(cycle_eos[i], f"{output}_cycle{n}_eos")
            for name, arr in ((f"{output}_cycle{n}_sos", cycle_sos[i]), (f"{output}_cycle{n}_eos", cycle_eos[i])):
                gs.run_command(
                    "r.support", map=name, title=f"t.crop.season cycle {n} " + name.rsplit("_", 1)[-1].upper(),
                    units="days since " + ref.strftime("%Y-%m-%d"),
                    history="t.crop.season multi-cycle output (-m)", quiet=True,
                )
        write_raster(ncycles.astype(np.float64), f"{output}_ncycles", categorical=True)
        write_raster(last_sos, f"{output}_last_sos")
        write_raster(last_eos, f"{output}_last_eos")
        write_raster(last_still_growing.astype(np.float64), f"{output}_last_still_growing", categorical=True)
        for name in (f"{output}_last_sos", f"{output}_last_eos"):
            gs.run_command(
                "r.support", map=name, title=f"t.crop.season {name.rsplit('_', 1)[-1].upper()} of last detected cycle",
                units="days since " + ref.strftime("%Y-%m-%d"),
                history="t.crop.season multi-cycle output (-m)", quiet=True,
            )
        gs.write_command(
            "r.category", map=f"{output}_last_still_growing", separator="pipe", rules="-",
            stdin="0|harvested (EOS observed)\n1|still growing (no EOS in period)\n", quiet=True,
        )
        gs.message(
            f"Multi-cycle outputs written: {output}_cycle1..{max_cycles}_sos/_eos, {output}_ncycles, "
            f"{output}_last_sos, {output}_last_eos, {output}_last_still_growing"
        )

    # --- Per-date development-stage classification --------------------------
    gs.message("Classifying development stage per date ...")
    stage_maps = []
    for d, dt in zip(optical_dates, ndvi_dt):
        day = (dt - ref).total_seconds() / 86400.0
        stage_arr = classify_stage(np.full(sos.shape, day), sos, pos, eos)
        stage_m = f"{output}_stage_{d.strftime('%Y%m%d')}"
        write_raster(stage_arr, stage_m, categorical=True)
        gs.run_command("r.colors", map=stage_m, color="bgyr", quiet=True)
        gs.write_command(
            "r.category", map=stage_m, separator="pipe", rules="-", stdin=STAGE_CATEGORY_RULES, quiet=True
        )
        stage_maps.append(stage_m)
    register_strds(
        f"{output}_stage", "Crop development stage",
        "Development stage classification computed by t.crop.season", stage_maps, ndvi_dt,
    )

    # --- Irrigation -----------------------------------------------------------
    # vv_stack/vh_stack/sar_days were already read above (shared with -m).
    gs.message("Computing Water Cloud Model soil backscatter anomaly ...")
    ndvi_on_sar = interp_to(sar_days, t_days, ndvi_stack)

    precip_recent = None
    if precip_strds:
        precip_maps = strds_maps(precip_strds, start, end)
        if precip_maps:
            precip_by_date = {d.date(): n for n, d in precip_maps}
            precip_all_dates = sorted(precip_by_date)
            precip_dt = [datetime.combine(d, datetime.min.time()) for d in precip_all_dates]
            precip_stack = read_stack([precip_by_date[d] for d in precip_all_dates])
            precip_days = days_since(precip_dt, ref)
            # sum precipitation over the 3 days preceding each SAR acquisition
            precip_recent = np.zeros((len(sar_days),) + precip_stack.shape[1:])
            for i, day in enumerate(sar_days):
                window = (precip_days >= day - 3) & (precip_days <= day)
                if window.any():
                    precip_recent[i] = np.nansum(precip_stack[window], axis=0)
        else:
            gs.warning("Precipitation STRDS has no maps in the given period; ignoring it.")

    irrigation = compute_irrigation(
        vv_stack, vh_stack, ndvi_on_sar, theta_deg, wcm_a, wcm_b,
        anomaly_threshold, precip_recent, rain_threshold,
    )

    anomaly_maps, flag_maps = [], []
    for i, d in enumerate(sar_dates):
        anomaly_m = f"{output}_vvanomaly_{d.strftime('%Y%m%d')}"
        flag_m = f"{output}_wetflag_{d.strftime('%Y%m%d')}"
        write_raster(irrigation["vv_anomaly_db"][i], anomaly_m)
        write_raster(irrigation["wetting_flag"][i], flag_m, categorical=True)
        gs.run_command("r.colors", map=anomaly_m, color="differences", quiet=True)
        gs.write_command(
            "r.category", map=flag_m, separator="pipe", rules="-",
            stdin="0|no wetting event\n1|irrigation event\n2|rain event\n", quiet=True,
        )
        anomaly_maps.append(anomaly_m)
        flag_maps.append(flag_m)

    register_strds(
        f"{output}_vvanomaly", "VV soil backscatter anomaly (dB above dry baseline)",
        "Water Cloud Model soil anomaly computed by t.crop.season", anomaly_maps, sar_dt,
    )
    register_strds(
        f"{output}_wetflag", "Wetting event flag (0=none, 1=irrigation, 2=rain)",
        "Wetting event classification computed by t.crop.season", flag_maps, sar_dt,
    )
    gs.message(
        f"Irrigation outputs written: STRDS {output}_vvanomaly, {output}_wetflag"
        + (" (rain-aware)" if precip_recent is not None else " (rain not distinguished - no precip= given)")
    )

    # --- Optional Random Forest classification -------------------------------
    if do_classify:
        train_and_classify(
            output=output,
            training=training,
            training_column=training_column,
            ndvi_maps=ndvi_maps,
            ndwi_maps=ndwi_maps,
            sos=sos, pos=pos, eos=eos, amplitude=amplitude,
            vvanomaly_stack=irrigation["vv_anomaly_db"],
            wetflag_stack=irrigation["wetting_flag"],
        )

    gs.message("t.crop.season finished.")
    return 0


def train_and_classify(
    output, training, training_column, ndvi_maps, ndwi_maps,
    sos, pos, eos, amplitude, vvanomaly_stack, wetflag_stack,
):
    """Train a Random Forest classifier on engineered features sampled at the
    training vector's points, then apply it to the full feature stack."""
    import numpy as np

    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        gs.fatal("scikit-learn is required for -c (pip install scikit-learn).")

    gs.message("Building feature stack for classification ...")

    # Cumulative NDVI/NDWI over the period (Pageot et al. style single feature
    # per index rather than a full time series) plus the phenology metrics and
    # a summary of the irrigation anomaly signal.
    ndvi_cum = f"{output}_feat_ndvi_cum"
    ndwi_cum = f"{output}_feat_ndwi_cum"
    gs.run_command("r.series", input=ndvi_maps, output=ndvi_cum, method="sum", overwrite=True, quiet=True)
    gs.run_command("r.series", input=ndwi_maps, output=ndwi_cum, method="sum", overwrite=True, quiet=True)

    vvanomaly_mean = np.nanmean(vvanomaly_stack, axis=0)
    vvanomaly_max = np.nanmax(vvanomaly_stack, axis=0)
    wetflag_count = np.nansum(wetflag_stack == 1, axis=0)

    feature_maps = {
        "sos": sos, "pos": pos, "eos": eos, "amplitude": amplitude,
        "vvanomaly_mean": vvanomaly_mean, "vvanomaly_max": vvanomaly_max,
        "wetflag_count": wetflag_count,
    }
    feature_names = list(feature_maps.keys()) + ["ndvi_cum", "ndwi_cum"]
    for name, arr in feature_maps.items():
        write_raster(arr, f"{output}_feat_{name}")

    all_feature_maps = [f"{output}_feat_{n}" for n in feature_maps] + [ndvi_cum, ndwi_cum]

    gs.message("Sampling features and labels at training locations ...")
    # v.to.points (type=point,centroid) keeps the source vector's attribute
    # table as-is on layer 1 (same cat, same table) - so training_column is
    # already present and we can add feature columns straight onto it,
    # no layer-2/join gymnastics needed.
    training_points = f"{output}_training_points_tmp"
    gs.run_command(
        "v.to.points", input=training, output=training_points,
        type="point,centroid", overwrite=True, quiet=True,
    )
    gs.run_command(
        "v.db.addcolumn", map=training_points,
        columns=",".join(f"{n} double precision" for n in feature_names), quiet=True,
    )
    for fmap, fname in zip(all_feature_maps, feature_names):
        gs.run_command("v.what.rast", map=training_points, raster=fmap, column=fname, quiet=True)

    columns = ["cat", training_column] + feature_names
    table = gs.read_command(
        "v.db.select", map=training_points, columns=",".join(columns), separator="|", quiet=True
    )
    rows = [line.split("|") for line in table.splitlines()[1:] if line.strip()]
    X_train, y_train = [], []
    for row in rows:
        try:
            label = row[1]
            feats = [float(v) for v in row[2:]]
        except (ValueError, IndexError):
            continue
        if any(f != f for f in feats):  # NaN check
            continue
        X_train.append(feats)
        y_train.append(label)

    if len(X_train) < 10:
        gs.fatal("Fewer than 10 usable training samples after feature sampling; aborting classification.")

    gs.message(f"Training Random Forest on {len(X_train)} samples, {len(feature_names)} features ...")
    clf = RandomForestClassifier(n_estimators=300, max_features="sqrt", n_jobs=-1, random_state=0)
    clf.fit(X_train, y_train)

    gs.message("Applying classifier to full raster stack ...")
    from grass.script import array as garray

    stack = np.stack([np.array(garray.array(mapname=m), dtype=np.float64) for m in all_feature_maps], axis=-1)
    rows_n, cols_n, n_feat = stack.shape
    flat = stack.reshape(-1, n_feat)
    valid = np.all(np.isfinite(flat), axis=1)

    labels_sorted = sorted(set(y_train))
    label_to_code = {label: i + 1 for i, label in enumerate(labels_sorted)}
    pred_codes = np.zeros(flat.shape[0])
    if valid.any():
        preds = clf.predict(flat[valid])
        pred_codes[valid] = [label_to_code[p] for p in preds]
    pred_codes[~valid] = np.nan
    classified = pred_codes.reshape(rows_n, cols_n)

    out_map = f"{output}_classified"
    write_raster(classified, out_map, categorical=True)
    cat_rules = "\n".join(f"{code}|{label}" for label, code in label_to_code.items()) + "\n"
    gs.write_command("r.category", map=out_map, separator="pipe", rules="-", stdin=cat_rules, quiet=True)
    gs.run_command("r.colors", map=out_map, color="random", quiet=True)
    gs.message(f"Classification written to raster map '{out_map}'")

    gs.run_command("g.remove", type="vector", name=training_points, flags="f", quiet=True)


if __name__ == "__main__":
    sys.exit(main())
