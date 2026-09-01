# gridpen

Power flow study on a radial 11 kV distribution feeder, built with pandapower.
Looks at two separate problems that get lumped together a lot in casual
discussion but are actually distinct: a feeder that's undervoltage at peak
load with zero solar involved, and a feeder that goes overvoltage at midday
once rooftop PV is added — and how much *where* you put that PV changes the
second problem.

## Background

Most "renewable integration" writeups I'd seen jumped straight to "adding
solar causes voltage rise," which is true but incomplete — it skips past
the fact that a lot of rural/semi-urban 11 kV feeders in India already sit
close to their voltage limits at peak load, before any solar enters the
picture. I wanted a model that could show both problems side by side and
make clear they don't have the same fix.

## The feeder

A 33/11 kV substation feeding a single radial spine of 16 buses, carrying a
mixed residential/agricultural/small-commercial load (~3.1 MW at peak).
Line parameters are set to match a typical ACSR conductor, and the load is
weighted heavier near the substation and sparser toward the tail, which is
roughly how these feeders actually look.

```python
# src/network.py builds this in pandapower
net = pp.create_empty_network()
bus_hv = pp.create_bus(net, vn_kv=33.0)
pp.create_ext_grid(net, bus=bus_hv, vm_pu=1.02)
# ... substation transformer, then 16 buses in a radial chain
```

## What gets tested

**Evening peak, no solar.** Full load, no generation anywhere on the feeder.
This just checks whether the feeder can hold statutory voltage limits
(0.94–1.06 pu) on its own load alone.

**Midday, low load, rising solar.** Load is scaled down to 40% of peak (a
reasonable daytime factor for a feeder that peaks in the evening), and PV
capacity is swept from 0% up to 200% of the feeder's peak load. This is
run twice — once with PV spread across all 16 buses in proportion to each
bus's own load, and once with PV all clustered onto the last 3 buses at the
tail end, since that's a common real pattern (that's usually where the
open land or big rooftops are).

## What came out of it

The feeder sags to **0.933 pu** at the tail end during evening peak — already
below the 0.94 pu floor — with no solar anywhere in the picture. That's just
line resistance over a long, thin radial spine. In practice this is a
conductor/regulator problem, not something rooftop solar caused or could fix.

![Feeder voltage sagging below the statutory floor at evening peak, no PV involved](charts/01_baseline_peak_voltage_profile.png)

Once you start adding midday solar, the first thing that happens isn't a
voltage violation — it's reverse power flow through the substation
transformer, which kicks in at around 50% penetration for either siting
strategy. The grid starts absorbing power from the feeder rather than
supplying it, well before voltage becomes an issue.

![Substation transformer flow flipping direction as PV output overtakes midday demand](charts/03_reverse_power_flow.png)

The part I found most useful is how much siting matters for hosting
capacity. Clustering PV at the tail end pushes the feeder past the 1.06 pu
ceiling at around 100% penetration. Spreading the same total PV capacity
across all 16 buses doesn't hit that ceiling until roughly 190% — almost
double the headroom for exactly the same amount of installed solar.

![Concentrated PV siting breaches the voltage ceiling at roughly half the penetration that distributed siting can tolerate](charts/02_voltage_rise_vs_penetration.png)

Looking at the full voltage profile along the feeder makes the mechanism
obvious — concentrated PV creates one big local voltage bump right at the
injection point, while distributed PV spreads that same effect thin enough
across the whole feeder that no single bus gets pushed too far.

![Voltage profile along the feeder, concentrated vs distributed PV siting, at several penetration levels](charts/05_voltage_profiles_by_siting.png)

## Layout

The whole thing is two source files plus one script that ties them together:

- `src/network.py` builds the feeder topology and load profile.
- `src/pv_integration.py` handles adding PV (either siting strategy), scaling
  load for the midday case, and running the actual power flow.
- `run_study.py` calls both of the above across all the scenarios, and drops
  the charts into `charts/` and the raw numbers into `outputs/`.

To run it:
```
pip install -r requirements.txt
python run_study.py
```


