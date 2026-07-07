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
confounded by soil moisture. Fusing both — as demonstrated across a
body of recent remote-sensing literature — gives more complete
phenology timing and opens the door to detecting irrigation events
from the SAR soil-moisture signal that optical data alone cannot see.

## What it computes

1. **Indices** per date: NDVI, NDWI, and the SAR cross-ratio (VH−VV, dB)
2. **Phenology** per pixel: SOS/POS/EOS/amplitude/season-length, from a
   double hyperbolic tangent fit to the NDVI time series (Meroni et
   al. 2021), with a fast vectorised threshold fallback (`-f`)
3. **Development stage** per date: a 6-class categorical raster
   (bare/pre-emergence → emergence → vegetative → peak → senescence →
   post-harvest) derived from each pixel's phenometrics
4. **Irrigation status**: a Water Cloud Model soil-backscatter anomaly
   and a wetting-event flag (irrigation vs. rain, if a precipitation
   STRDS is supplied), following Ma, Johansen & McCabe (2022)
5. **Optional Random Forest classification** (`-c`) trained on the
   above engineered features plus a user-supplied labeled vector

See [t.crop.season.md](t.crop.season.md) for the full option
reference, formulas, and literature references.

## Installing

```
git clone https://github.com/YannChemin/t.crop.season.git
make MODULE_TOPDIR=$HOME/dev/grass
```

or, from within a running GRASS session:

```
g.extension extension=t.crop.season url=/path/to/t.crop.season
```

Requires `numpy` and `scipy`; the optional `-c` classification flag
additionally requires `scikit-learn`.

## License

Public domain (Unlicense) — see [LICENSE](LICENSE).
