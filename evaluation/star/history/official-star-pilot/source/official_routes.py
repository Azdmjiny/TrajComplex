"""Official WSSS RWY 20 RNAV STAR routes transcribed from CAAS AIP charts.

Fix coordinates are taken from the chart labels (raw text extraction) and are
consistent across every chart that prints them. Route sequences are taken from
the AIP back-page tabular descriptions. Only the six RWY20 RNAV STARs relevant
to the evaluation's final heading (about 247 deg) are included.
"""
from __future__ import annotations

import math

import numpy as np

A, E2 = 6378137.0, 6.69437999014e-3
LAT0, LON0, H0 = math.radians(1.3592111111111111), math.radians(103.989325), 6.66


def llh_to_enu(lat, lon, h):
    """WGS84 geodetic to the same Changi ENU frame used by the evaluation."""
    lat, lon, h = np.radians(lat), np.radians(lon), np.asarray(h, float)

    def ecef(phi, lam, alt):
        n = A / np.sqrt(1 - E2 * np.sin(phi) ** 2)
        return np.stack(((n + alt) * np.cos(phi) * np.cos(lam),
                         (n + alt) * np.cos(phi) * np.sin(lam),
                         (n * (1 - E2) + alt) * np.sin(phi)), axis=-1)

    p = ecef(lat, lon, h)
    o = ecef(np.asarray(LAT0), np.asarray(LON0), np.asarray(H0))
    d = p - o
    sl, cl, so, co = math.sin(LAT0), math.cos(LAT0), math.sin(LON0), math.cos(LON0)
    return np.stack((-so * d[..., 0] + co * d[..., 1],
                     -sl * co * d[..., 0] - sl * so * d[..., 1] + cl * d[..., 2],
                     cl * co * d[..., 0] + cl * so * d[..., 1] + sl * d[..., 2]), axis=-1)

# name: (lat_deg, lon_deg), transcribed from the AIP chart labels.
FIXES = {
    "ARAMA": (1.6150, 103.1200), "ASUNA": (0.9967, 103.1650),
    "BOBAG": (1.0417, 103.4983), "SAMKO": (1.0917, 103.8819),
    "DOVAN": (1.3272, 104.2136), "BIPOP": (1.5228, 104.1717),
    "TOMAN": (1.3631, 105.7881), "KARTO": (1.1900, 105.5619),
    "KEXAS": (1.1719, 104.8050), "LAVAX": (1.1639, 104.4539),
    "RUVIK": (1.2394, 104.3425), "OBDOS": (0.4175, 106.9308),
    "IKAGO": (0.6378, 105.4919), "IKIMA": (0.7206, 104.9167),
    "IBULA": (0.8433, 104.6000), "REPOV": (0.2731, 104.0500),
    "REMES": (0.7283, 103.9597), "ELALO": (4.2111, 104.5581),
    "KANLA": (3.7656, 104.6017), "KILOT": (3.0381, 104.6731),
    "PIBAP": (2.5064, 104.1050), "PASPU": (1.9875, 104.1050),
    "NYLON": (1.6158, 104.1067),
}
SEQUENCES = {
    "ARAMA 1B": ["ARAMA", "BOBAG", "SAMKO", "DOVAN", "BIPOP"],
    "ASUNA 1B": ["ASUNA", "BOBAG", "SAMKO", "DOVAN", "BIPOP"],
    "KARTO 1B": ["TOMAN", "KARTO", "KEXAS", "LAVAX", "RUVIK", "DOVAN", "BIPOP"],
    "OBDOS 1B": ["OBDOS", "IKAGO", "IKIMA", "IBULA", "LAVAX", "RUVIK", "DOVAN", "BIPOP"],
    "REPOV 1B": ["REPOV", "REMES", "DOVAN", "BIPOP"],
    "ELALO 1B": ["ELALO", "KANLA", "KILOT", "PIBAP", "PASPU", "NYLON"],
}


def route(name):
    fixes = [FIXES[fix] for fix in SEQUENCES[name]]
    lat = np.array([fix[0] for fix in fixes])
    lon = np.array([fix[1] for fix in fixes])
    enu = llh_to_enu(lat, lon, np.zeros(len(fixes)))
    xy = np.column_stack([enu[:, 0], enu[:, 1]])
    # The STAR ends at an IAF; append the airport reference so a complete
    # arrival track can be projected. This is a coarse extension, not an
    # official approach procedure.
    if np.linalg.norm(xy[-1]) > 2000:
        xy = np.vstack([xy, np.zeros(2)])
    return xy


def routes():
    return {name: route(name) for name in SEQUENCES}
