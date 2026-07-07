#!/usr/bin/env python3
# Test for t.crop.season
# Requires: GRASS GIS session (any projected or lat/lon location)
# Uses synthetic Sentinel-1/2-like time series, no network access needed.

import unittest
from datetime import datetime, timedelta

from grass.gunittest.case import TestCase
from grass.gunittest.main import test


class TestTCropSeason(TestCase):
    """Tests for t.crop.season module."""

    output_prefix = "test_tcs"
    start_date = datetime(2023, 4, 1)

    @classmethod
    def setUpClass(cls):
        cls.use_temp_region()
        cls.runModule("g.region", n=5, s=0, e=5, w=0, res=1)

        import grass.script as gs
        import grass.temporal as tgis

        tgis.init()

        red_maps, nir_maps, swir_maps = [], [], []
        for i in range(10):
            d = cls.start_date + timedelta(days=8 * i)
            t = 8 * i
            # simple logistic green-up, no decay within the test window
            ndvi_expr = f"0.15 + 0.55 / (1 + exp(-0.12 * ({t} - 25)))"
            red_m, nir_m, swir_m = (
                f"{cls.output_prefix}_red_{i}",
                f"{cls.output_prefix}_nir_{i}",
                f"{cls.output_prefix}_swir_{i}",
            )
            cls.runModule(
                "r.mapcalc",
                expression=f"__ndvi_tmp = {ndvi_expr}",
                overwrite=True,
            )
            cls.runModule(
                "r.mapcalc", expression=f"{nir_m} = 1000.0 * (1 + __ndvi_tmp)", overwrite=True
            )
            cls.runModule(
                "r.mapcalc", expression=f"{red_m} = 1000.0 * (1 - __ndvi_tmp)", overwrite=True
            )
            cls.runModule(
                "r.mapcalc", expression=f"{swir_m} = 800.0 * (1 - 0.3 * __ndvi_tmp)", overwrite=True
            )
            cls.runModule("r.timestamp", map=red_m, date=d.strftime("%d %b %Y 00:00:00"))
            cls.runModule("r.timestamp", map=nir_m, date=d.strftime("%d %b %Y 00:00:00"))
            cls.runModule("r.timestamp", map=swir_m, date=d.strftime("%d %b %Y 00:00:00"))
            red_maps.append(red_m)
            nir_maps.append(nir_m)
            swir_maps.append(swir_m)

        vv_maps, vh_maps = [], []
        for i in range(12):
            d = cls.start_date + timedelta(days=7 * i)
            vv_m, vh_m = f"{cls.output_prefix}_vv_{i}", f"{cls.output_prefix}_vh_{i}"
            cls.runModule("r.mapcalc", expression=f"{vv_m} = -12.0 + rand(-0.5, 0.5)", overwrite=True, seed=1)
            cls.runModule("r.mapcalc", expression=f"{vh_m} = -18.0 + rand(-0.5, 0.5)", overwrite=True, seed=2)
            cls.runModule("r.timestamp", map=vv_m, date=d.strftime("%d %b %Y 00:00:00"))
            cls.runModule("r.timestamp", map=vh_m, date=d.strftime("%d %b %Y 00:00:00"))
            vv_maps.append(vv_m)
            vh_maps.append(vh_m)

        cls.runModule("g.remove", type="raster", name="__ndvi_tmp", flags="f")

        for name, maps in (
            ("test_red", red_maps),
            ("test_nir", nir_maps),
            ("test_swir", swir_maps),
            ("test_vv", vv_maps),
            ("test_vh", vh_maps),
        ):
            cls.runModule(
                "t.create", type="strds", temporaltype="absolute", output=name,
                title=name, description=name, overwrite=True,
            )
            cls.runModule(
                "t.register", type="raster", input=name, maps=",".join(maps), overwrite=True,
            )

    @classmethod
    def tearDownClass(cls):
        import grass.script as gs

        cls.del_temp_region()
        mapset = gs.gisenv()["MAPSET"]

        rasters = gs.list_grouped("raster").get(mapset, [])
        to_remove = [m for m in rasters if m.startswith(cls.output_prefix) or m.startswith("test_")]
        if to_remove:
            gs.run_command("g.remove", type="raster", name=",".join(to_remove), flags="f")

        import grass.temporal as tgis

        tgis.init()
        for etype in ("strds",):
            existing = gs.read_command(
                "t.list", type=etype, columns="name", quiet=True
            ).splitlines()
            to_remove_t = [s for s in existing if s.startswith(cls.output_prefix) or s.startswith("test_")]
            if to_remove_t:
                gs.run_command("t.remove", type=etype, inputs=",".join(to_remove_t), flags="rf", quiet=True)

    def test_fast_mode_runs_and_produces_outputs(self):
        self.assertModule(
            "t.crop.season",
            red="test_red", nir="test_nir", swir="test_swir",
            vv="test_vv", vh="test_vh",
            start="2023-04-01", end="2023-10-01",
            output=self.output_prefix, flags="f", overwrite=True,
        )

        import grass.script as gs

        rasters = gs.list_grouped("raster")[gs.gisenv()["MAPSET"]]
        for suffix in ("_sos", "_pos", "_eos", "_amplitude", "_season_length"):
            self.assertTrue(
                any(r.startswith(self.output_prefix + suffix) for r in rasters),
                f"expected a raster named like {self.output_prefix}{suffix}",
            )

        strds_list = gs.read_command("t.list", type="strds", quiet=True).splitlines()
        for suffix in ("_ndvi", "_ndwi", "_cr", "_stage", "_vvanomaly", "_wetflag"):
            self.assertTrue(
                any(s.startswith(self.output_prefix + suffix) for s in strds_list),
                f"expected a STRDS named like {self.output_prefix}{suffix}",
            )

    def test_sos_is_within_data_range(self):
        import grass.script as gs

        info = gs.parse_command("r.univar", map=f"{self.output_prefix}_sos", flags="g")
        self.assertGreaterEqual(float(info["min"]), 0)
        self.assertLessEqual(float(info["max"]), 72)  # last optical date, day 72


if __name__ == "__main__":
    test()
