# t.crop.season

A [GRASS GIS](https://grass.osgeo.org/) addon that derives **crop
development stage** and **irrigation status** from fused Sentinel-1 SAR
and Sentinel-2 optical time series (Space-Time Raster Datasets, STRDS)
over a user-defined period of interest.

```
t.crop.season red=s2_B04 nir=s2_B08 swir=s2_B11 \
              vv=s1_VV vh=s1_VH \
              start=2023-03-01 end=2023-10-01 \
              output=field2023
```

It is designed to sit downstream of
[r.in.sentinel](https://github.com/YannChemin/r.in.sentinel), which
imports Sentinel-1/2 scenes and can register them directly as
per-band STRDS (`strds=` option) with the naming this module expects.

## Why

Individually, optical and SAR time series each carry partial
information about a crop's growth: NDVI tracks chlorophyll/canopy
cover but is blind on cloudy days; VV/VH backscatter is
cloud-independent and structurally sensitive but noisier and
confounded by soil moisture. Fusing both, as demonstrated across a
body of recent remote-sensing literature (see [References](#references)),
gives more complete phenology timing and opens the door to detecting
irrigation events from the SAR soil-moisture signal that optical data
cannot see. `t.crop.season` implements that fusion as a single GRASS
temporal-framework tool.

## What it computes

### 1. Indices (per acquisition date)

- **NDVI** = (NIR − Red) / (NIR + Red)
- **NDWI** = (NIR − SWIR) / (NIR + SWIR) (Gao 1996 formulation)
- **CR** (SAR cross-ratio) = VH − VV, in dB

Each is registered as its own output STRDS (`<output>_ndvi`,
`<output>_ndwi`, `<output>_cr`).

### 2. Phenology (per pixel, over the whole period)

By default, `t.crop.season` fits the **double hyperbolic tangent**
phenology model of Meroni et al. (2021) to each pixel's NDVI time
series:

```
VI(t) = a0 + a1*(tanh((t-a2)*a3)+1)/2 + a4*(tanh((t-a5)*a6)+1)/2 - a4
```

where `a0` is the background/bare-soil level, `a1`/`a4` are the
green-up/decay amplitudes, `a2`/`a5` the inflection timings and
`a3`/`a6` the steepness of green-up/senescence. The fit is fed the
same amplitude-threshold estimate used as its initial guess (see
below), so a converged fit and its fallback agree closely near the
crossing points; the fit mainly resolves the noise the raw threshold
crossing is sensitive to.

From the fitted (or fallback) curve, three phenometrics are derived
using a configurable fraction of the seasonal amplitude
(`sos_fraction=`, default 50%, matching Meroni et al.'s SOS50/EOS50):

- **SOS** — start of season (rising crossing)
- **POS** — peak of season (curve maximum)
- **EOS** — end of season (falling crossing)
- **amplitude** and **season_length** (= EOS − SOS) are also written

If a pixel has too few valid observations, too little seasonal
amplitude, or the nonlinear fit does not converge, the module falls
back to the same threshold crossing computed directly on the raw
(unfitted) percentile-normalised series, rather than leaving the
pixel empty.

Pass **`-f`** (fast mode) to skip the per-pixel curve fit everywhere
and use the vectorised amplitude-threshold method only — much faster
on large regions, at some cost in noise robustness.

### 3. Per-date development-stage classification

Each optical acquisition date is classified, per pixel, into one of six
stages based on its position relative to that pixel's SOS/POS/EOS:

| code | stage |
|------|-------|
| 0 | bare / pre-emergence |
| 1 | emergence / early vegetative |
| 2 | vegetative |
| 3 | reproductive / peak |
| 4 | senescence |
| 5 | post-harvest / bare |

Written as the `<output>_stage` STRDS.

### 4. Irrigation status (Water Cloud Model soil anomaly)

For each SAR acquisition date, `t.crop.season` estimates vegetation
water content from NDVI (interpolated onto the SAR date axis),
following Ma, Johansen & McCabe (2022):

```
VWC = 0.098 * exp(4.225 * NDVI)
```

and inverts the Water Cloud Model (Attema & Ulaby 1978; Bindlish &
Barros parameterisation `wcm_a=`/`wcm_b=`, default A=0.0012, B=0.091)
to isolate the soil-driven backscatter component from the observed VV
(and VH) backscatter:

```
tau2       = exp(-2 * wcm_b * VWC / cos(theta))
sigma_veg  = wcm_a * VWC * cos(theta) * (1 - tau2)
sigma_soil = (sigma_obs_linear - sigma_veg) / tau2
```

Each pixel's driest observed soil-backscatter level (10th percentile
over the period) is taken as a dry-soil baseline; the anomaly above
that baseline, in dB, is written as the `<output>_vvanomaly` STRDS.
Where the anomaly exceeds `anomaly_threshold=` (default 1.5 dB), a
wetting event is flagged in `<output>_wetflag`:

| code | meaning |
|------|---------|
| 0 | no wetting event |
| 1 | irrigation event |
| 2 | rain event |

Rain and irrigation produce the same backscatter signature and cannot
be told apart from SAR alone. If an optional **`precip=`** STRDS is
supplied (e.g. from
[t.in.era5](https://github.com/YannChemin/t.in.era5)), wetting events
that coincide with more than `rain_threshold=` mm (default 2 mm,
summed over the 3 days before the SAR date) of precipitation are
reclassified as rain (code 2) rather than irrigation (code 1). Without
`precip=`, all wetting events are reported as irrigation and this
caveat is logged as a warning.

### 5. Optional Random Forest classification (`-c`)

If a labeled **`training=`** vector (points or polygons; polygons are
converted to centroids) with a **`training_column=`** attribute is
supplied, `-c` trains a scikit-learn `RandomForestClassifier` on a
feature stack built from this module's own outputs — cumulative
NDVI/NDWI over the period (Pageot et al. 2020 style), the phenology
metrics (SOS/POS/EOS/amplitude), and summary statistics of the
irrigation anomaly signal (mean/max anomaly, wetting-event count) —
and applies it to the full raster to produce `<output>_classified`.
This mirrors the irrigated/rainfed classification approach of Pageot
et al. (2020) without hard-coding it to that one use case: the same
mechanism works for any two-or-more-class label set (e.g. crop type,
growth-stage anomaly, water-stress class) the user's training data
defines.

## Output naming

Given `output=field2023`:

- STRDS: `field2023_ndvi`, `field2023_ndwi`, `field2023_cr`,
  `field2023_stage`, `field2023_vvanomaly`, `field2023_wetflag`
- Single-raster phenometrics: `field2023_sos`, `field2023_pos`,
  `field2023_eos`, `field2023_amplitude`, `field2023_season_length`
- With `-c`: `field2023_classified` (plus intermediate
  `field2023_feat_*` feature rasters)

## Notes and limitations

- Requires `numpy` and `scipy`; `-c` additionally requires
  `scikit-learn`.
- Reads each input raster fully into memory via
  `grass.script.array`, so processing time and memory scale with
  region size × number of dates; use `-f` and/or a coarser region for
  quick exploration before running the full fit.
- The incidence angle (`theta=`) is treated as a single scalar for the
  whole region; for large regions spanning a wide swath, consider
  running per-tile with a locally appropriate value.
- `red`/`nir`/`swir` must share acquisition dates (as produced by
  `r.in.sentinel`, which imports one raster per band per date); `vv`
  and `vh` likewise.

## References

- Meroni, M. et al. (2021). *Comparing land surface phenology of major
  European crops as derived from SAR and multispectral data of
  Sentinel-1 and -2.* Remote Sensing of Environment, 253.
  (double hyperbolic tangent model, SOS50/EOS50/PS90)
- Ma, H., Johansen, K. & McCabe, M.F. (2022). *Monitoring Irrigation
  Events and Crop Dynamics Using Sentinel-1 and Sentinel-2 Time
  Series.* Remote Sensing, 14(5), 1205. (Water Cloud Model
  parameterisation, VWC-from-NDVI formula, irrigation-event detection
  logic)
- Pageot, Y. et al. (2020). *Detection of Irrigated and Rainfed Crops
  in Temperate Areas Using Sentinel-1 and Sentinel-2 Time Series.*
  Remote Sensing, 12(18), 3044. (cumulative-index feature engineering
  for irrigation classification)
- d'Andrimont, R. et al. (2021). *From parcel to continental scale — A
  first European crop type map based on Sentinel-1 and LUCAS
  Copernicus in-situ observations.* Remote Sensing of Environment, 266.
  (Random Forest crop classification from VV/VH time series)
- Veloso, A. et al. (2017). *Understanding the temporal behavior of
  crops using Sentinel-1 and Sentinel-2-like data for agricultural
  applications.* Remote Sensing of Environment, 199.
  (crop-specific VV/VH/NDVI correlation behaviour by phenological
  stage)
- Harfenmeister, K. et al. (2021). *Detecting Phenological Development
  of Winter Wheat and Winter Barley Using Time Series of Sentinel-1
  and Sentinel-2.* Remote Sensing, 13(24), 5036. (breakpoint-based
  phenology detection, BBCH linkage)
- Xie, Q. & Niculescu, S. (2022). *Mapping Crop Types and Monitoring
  Their Phenology Using Sentinel-1 and Sentinel-2.* Remote Sensing,
  14(18), 4437. (backscatter-shape based germination/heading/harvest
  detection)

## See also

- [r.in.sentinel](https://github.com/YannChemin/r.in.sentinel) —
  imports the Sentinel-1/2 STRDS this module consumes
- [t.in.era5](https://github.com/YannChemin/t.in.era5) — a source of
  the optional `precip=` STRDS
- *t.rast.\** family of GRASS temporal addons
