"""
pv_integration.py
------------------
Adds rooftop/distributed solar PV to the feeder built in network.py and runs
power-flow studies across a range of penetration levels and two siting
strategies:

  - "concentrated": all PV capacity lumped onto the last few (tail-end) buses,
    representative of a cluster of large rooftop/commercial solar installs
    at the far end of a feeder (a common real-world siting pattern, since
    open land / large rooftops are often at the rural tail end).

  - "distributed": PV capacity spread across every load bus in proportion
    to that bus's own load, representative of organic, feeder-wide rooftop
    solar adoption.

Two load conditions are studied, since PV-related voltage problems and
feeder undervoltage problems are two DIFFERENT phenomena that occur at
different times of day:

  - "evening_peak": full load, zero solar (worst case for undervoltage /
    thermal loading — no PV contribution at all).
  - "midday_low_load": load scaled down to a typical daytime factor,
    solar penetration swept upward (worst case for overvoltage / reverse
    power flow, since generation is highest exactly when demand is lowest).
"""

import numpy as np
import pandapower as pp

from network import build_feeder, total_peak_load_kw, BASE_LOAD_KW

MIDDAY_LOAD_FACTOR = 0.40   # daytime load as a fraction of evening peak
V_MIN_PU = 0.94             # CEA/typical DISCOM statutory lower limit (-6%)
V_MAX_PU = 1.06             # statutory upper limit (+6%)


def reset_pv(net):
    """Remove any existing static generators (PV) from the network."""
    net.sgen.drop(net.sgen.index, inplace=True)


def add_pv(net, load_buses, penetration_pct, siting="distributed", n_concentrated=3):
    """
    Add PV capacity to the network.

    penetration_pct: total installed PV capacity as a percentage of the
        feeder's total EVENING PEAK load (kW), regardless of siting.
        e.g. 50 -> total PV nameplate = 0.5 * total_peak_load_kw()
    siting: "distributed" spreads PV across all load buses proportional to
        each bus's own peak load. "concentrated" lumps all PV onto the
        last `n_concentrated` buses (tail end of the feeder), split
        evenly among them.
    """
    reset_pv(net)
    total_pv_kw = (penetration_pct / 100.0) * total_peak_load_kw()

    if siting == "distributed":
        weights = BASE_LOAD_KW / BASE_LOAD_KW.sum()
        for bus, w in zip(load_buses, weights):
            pv_kw = total_pv_kw * w
            if pv_kw > 0:
                pp.create_sgen(net, bus=bus, p_mw=pv_kw / 1000.0, q_mvar=0.0,
                                name=f"PV@bus{bus}")
    elif siting == "concentrated":
        tail_buses = load_buses[-n_concentrated:]
        pv_each_kw = total_pv_kw / n_concentrated
        for bus in tail_buses:
            pp.create_sgen(net, bus=bus, p_mw=pv_each_kw / 1000.0, q_mvar=0.0,
                            name=f"PV@bus{bus}")
    else:
        raise ValueError("siting must be 'distributed' or 'concentrated'")

    return net


def scale_load(net, factor):
    """Scale all loads on the network by a constant factor (e.g. daytime load factor)."""
    net.load["p_mw"] = net.load["p_mw"] * factor
    net.load["q_mvar"] = net.load["q_mvar"] * factor
    return net


def run_case(penetration_pct, siting, load_factor):
    """Build a fresh network, apply load factor + PV, run power flow, return results dict."""
    net, load_buses = build_feeder()
    scale_load(net, load_factor)
    add_pv(net, load_buses, penetration_pct, siting=siting)

    pp.runpp(net)

    vm = net.res_bus.vm_pu.values[1:]  # exclude substation bus (index 0 is HV bus... actually bus 0 is HV, 1 is MV substation)
    # bus indices: 0=HV, 1=MV substation, 2..17 = load buses
    load_bus_v = net.res_bus.vm_pu.values[2:]

    trafo_p_hv_mw = net.res_trafo.p_hv_mw.values[0]  # +ve = power flowing INTO feeder from grid
    line_loading_pct = net.res_line.loading_percent.values
    losses_kw = net.res_line.pl_mw.sum() * 1000.0 + net.res_trafo.pl_mw.sum() * 1000.0

    return {
        "penetration_pct": penetration_pct,
        "siting": siting,
        "load_factor": load_factor,
        "v_min_pu": float(load_bus_v.min()),
        "v_max_pu": float(load_bus_v.max()),
        "v_tail_pu": float(load_bus_v[-1]),
        "trafo_p_hv_mw": float(trafo_p_hv_mw),
        "reverse_flow": bool(trafo_p_hv_mw < 0),
        "max_line_loading_pct": float(line_loading_pct.max()),
        "losses_kw": float(losses_kw),
        "bus_voltages": load_bus_v.tolist(),
    }
