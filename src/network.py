"""
network.py
----------
Builds a synthetic 11 kV radial distribution feeder representative of a
semi-urban Indian DISCOM feeder, using pandapower.

Topology: 33/11 kV substation -> 11 kV radial feeder with 16 load buses
in a single long radial spine (worst case for voltage drop, which is the
realistic case for rural/semi-urban LV-side feeders in India).

All parameters (line lengths, conductor type, load sizes) are illustrative
but dimensioned to sit within realistic ranges for an 11 kV feeder serving
a mixed residential/agricultural/small-commercial load of ~3-4 MW peak.
"""

import pandapower as pp
import numpy as np

# ---------------------------------------------------------------------
# Feeder parameters
# ---------------------------------------------------------------------
N_BUSES = 16                 # number of 11kV load buses downstream of substation
SPAN_KM = 0.6                # average line span between consecutive buses (km)
HV_KV = 33.0
MV_KV = 11.0

# Per-bus peak load (kW) - mixed residential/agri/commercial profile,
# heavier near the substation, tapering off towards the feeder end,
# with a couple of larger agricultural pump-load buses mixed in.
np.random.seed(42)
BASE_LOAD_KW = np.array([
    280, 220, 260, 300, 180, 240,   # near substation - denser load
    150, 320, 140, 200, 260, 120,   # mid-feeder incl. an agri pump load (bus 8)
    90,  150, 70,  110              # tail end - sparse, rural
])
LOAD_PF = 0.90  # typical lagging power factor for mixed load


def build_feeder():
    """Build and return a pandapower network object for the 11kV radial feeder."""
    net = pp.create_empty_network(name="regional_11kV_feeder")

    # Slack / HV grid connection bus (33 kV)
    bus_hv = pp.create_bus(net, vn_kv=HV_KV, name="33kV Grid Bus")
    pp.create_ext_grid(net, bus=bus_hv, vm_pu=1.02, name="Upstream Grid")

    # 33/11 kV substation bus
    bus_mv_source = pp.create_bus(net, vn_kv=MV_KV, name="11kV Substation Bus")
    pp.create_transformer(
        net, hv_bus=bus_hv, lv_bus=bus_mv_source,
        std_type="25 MVA 110/20 kV",  # placeholder std type, sized below
        name="Substation Transformer"
    )
    # Override with a more appropriate 33/11kV, ~6.3 MVA transformer rating
    net.trafo.loc[0, "sn_mva"] = 6.3
    net.trafo.loc[0, "vn_hv_kv"] = HV_KV
    net.trafo.loc[0, "vn_lv_kv"] = MV_KV
    net.trafo.loc[0, "vk_percent"] = 8.0
    net.trafo.loc[0, "vkr_percent"] = 0.9
    net.trafo.loc[0, "pfe_kw"] = 7.0
    net.trafo.loc[0, "i0_percent"] = 0.3

    # Radial chain of 11kV buses
    bus_ids = [bus_mv_source]
    for i in range(N_BUSES):
        b = pp.create_bus(net, vn_kv=MV_KV, name=f"Bus {i+1}")
        bus_ids.append(b)

    # Lines connecting the radial chain — Dog conductor equivalent (~0.35 ohm/km, 0.35 mH/km typical for 11kV ACSR)
    for i in range(N_BUSES):
        pp.create_line_from_parameters(
            net,
            from_bus=bus_ids[i],
            to_bus=bus_ids[i + 1],
            length_km=SPAN_KM,
            r_ohm_per_km=0.35,
            x_ohm_per_km=0.35,
            c_nf_per_km=10.0,
            max_i_ka=0.30,   # ~300A rated ACSR Dog conductor
            name=f"Line {i+1}"
        )

    # Loads at each downstream bus
    for i in range(N_BUSES):
        p_kw = BASE_LOAD_KW[i]
        q_kvar = p_kw * np.tan(np.arccos(LOAD_PF))
        pp.create_load(
            net, bus=bus_ids[i + 1],
            p_mw=p_kw / 1000.0, q_mvar=q_kvar / 1000.0,
            name=f"Load {i+1}"
        )

    return net, bus_ids[1:]  # return net and list of the 16 load-bus indices (excludes substation bus)


def total_peak_load_kw():
    return float(BASE_LOAD_KW.sum())


if __name__ == "__main__":
    net, load_buses = build_feeder()
    pp.runpp(net)
    print(net.res_bus.vm_pu)
    print("Total peak load (kW):", total_peak_load_kw())
