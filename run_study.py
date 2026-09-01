"""
run_study.py
------------
Main entry point for the power-flow / renewable-integration study.

Studies performed:
  1. Baseline evening-peak load flow (no PV) -> voltage profile along feeder.
  2. Midday low-load PV penetration sweep (0-200% of peak load), for both
     "distributed" and "concentrated" siting strategies -> voltage rise,
     reverse power flow onset, and losses vs. penetration.
  3. Voltage profile snapshots along the feeder at selected penetration
     levels, for both siting strategies.

Outputs: CSVs in outputs/, charts (PNG) in charts/.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pv_integration import run_case, V_MIN_PU, V_MAX_PU, MIDDAY_LOAD_FACTOR
from network import total_peak_load_kw, N_BUSES

OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
CHART_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

PENETRATIONS = list(range(0, 201, 10))  # 0% to 200% of peak load, in 10% steps
SITINGS = ["distributed", "concentrated"]


def study_1_baseline_peak():
    print("Study 1: Baseline evening-peak load flow (no PV)...")
    r = run_case(penetration_pct=0, siting="distributed", load_factor=1.0)
    df = pd.DataFrame({
        "bus": list(range(1, N_BUSES + 1)),
        "vm_pu": r["bus_voltages"],
    })
    df.to_csv(os.path.join(OUT_DIR, "baseline_peak_voltage_profile.csv"), index=False)

    plt.figure(figsize=(8, 5))
    plt.plot(df["bus"], df["vm_pu"], marker="o", color="#c0392b", label="Voltage profile (evening peak, no PV)")
    plt.axhline(V_MIN_PU, color="gray", linestyle="--", label=f"Statutory min ({V_MIN_PU} pu)")
    plt.axhline(V_MAX_PU, color="gray", linestyle=":", label=f"Statutory max ({V_MAX_PU} pu)")
    plt.xlabel("Bus number (1 = closest to substation, 16 = feeder end)")
    plt.ylabel("Voltage (pu)")
    plt.title("Baseline Feeder Voltage Profile at Evening Peak Load (No PV)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "01_baseline_peak_voltage_profile.png"), dpi=150)
    plt.close()

    print(f"  Tail-end voltage at peak load: {r['v_tail_pu']:.4f} pu "
          f"({'BELOW' if r['v_tail_pu'] < V_MIN_PU else 'within'} statutory limit)")
    return r


def study_2_pv_sweep():
    print("Study 2: Midday PV penetration sweep (distributed vs concentrated siting)...")
    rows = []
    for siting in SITINGS:
        for pct in PENETRATIONS:
            r = run_case(penetration_pct=pct, siting=siting, load_factor=MIDDAY_LOAD_FACTOR)
            rows.append(r)
    df = pd.DataFrame(rows).drop(columns=["bus_voltages"])
    df.to_csv(os.path.join(OUT_DIR, "pv_penetration_sweep.csv"), index=False)

    # --- Chart: max feeder voltage vs. penetration, both siting strategies ---
    plt.figure(figsize=(8, 5))
    for siting, color in zip(SITINGS, ["#2980b9", "#e67e22"]):
        sub = df[df.siting == siting]
        plt.plot(sub.penetration_pct, sub.v_max_pu, marker="o", color=color, label=f"{siting.capitalize()} PV siting")
    plt.axhline(V_MAX_PU, color="red", linestyle="--", label=f"Statutory max ({V_MAX_PU} pu)")
    plt.xlabel("PV penetration (% of feeder peak load, midday low-load condition)")
    plt.ylabel("Max feeder voltage (pu)")
    plt.title("Voltage Rise vs. PV Penetration: Distributed vs. Concentrated Siting")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "02_voltage_rise_vs_penetration.png"), dpi=150)
    plt.close()

    # --- Chart: transformer power flow (reverse power flow onset) ---
    plt.figure(figsize=(8, 5))
    for siting, color in zip(SITINGS, ["#2980b9", "#e67e22"]):
        sub = df[df.siting == siting]
        plt.plot(sub.penetration_pct, sub.trafo_p_hv_mw, marker="o", color=color, label=f"{siting.capitalize()} PV siting")
    plt.axhline(0, color="black", linestyle="-", linewidth=1)
    plt.xlabel("PV penetration (% of feeder peak load, midday low-load condition)")
    plt.ylabel("Substation transformer power flow (MW, +ve = import from grid)")
    plt.title("Reverse Power Flow Onset at Substation vs. PV Penetration")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "03_reverse_power_flow.png"), dpi=150)
    plt.close()

    # --- Chart: feeder losses vs. penetration ---
    plt.figure(figsize=(8, 5))
    for siting, color in zip(SITINGS, ["#2980b9", "#e67e22"]):
        sub = df[df.siting == siting]
        plt.plot(sub.penetration_pct, sub.losses_kw, marker="o", color=color, label=f"{siting.capitalize()} PV siting")
    plt.xlabel("PV penetration (% of feeder peak load, midday low-load condition)")
    plt.ylabel("Total feeder + transformer losses (kW)")
    plt.title("Network Losses vs. PV Penetration")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "04_losses_vs_penetration.png"), dpi=150)
    plt.close()

    # --- Find and report violation thresholds ---
    summary = {}
    for siting in SITINGS:
        sub = df[df.siting == siting].sort_values("penetration_pct")
        violated = sub[sub.v_max_pu > V_MAX_PU]
        threshold = violated.penetration_pct.min() if not violated.empty else None
        reverse = sub[sub.reverse_flow]
        reverse_threshold = reverse.penetration_pct.min() if not reverse.empty else None
        summary[siting] = {"voltage_violation_pct": threshold, "reverse_flow_onset_pct": reverse_threshold}
        print(f"  [{siting}] Reverse power flow onset: {reverse_threshold}% penetration | "
              f"Overvoltage (>{V_MAX_PU} pu) onset: {threshold}% penetration")

    return df, summary


def study_3_voltage_profiles_at_penetrations():
    print("Study 3: Voltage profile snapshots at selected PV penetration levels...")
    snapshot_levels = [0, 50, 100, 150, 200]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for ax, siting in zip(axes, SITINGS):
        for pct in snapshot_levels:
            r = run_case(penetration_pct=pct, siting=siting, load_factor=MIDDAY_LOAD_FACTOR)
            ax.plot(range(1, N_BUSES + 1), r["bus_voltages"], marker="o", label=f"{pct}% PV")
        ax.axhline(V_MAX_PU, color="red", linestyle="--", linewidth=1, label=f"Max limit ({V_MAX_PU} pu)")
        ax.axhline(V_MIN_PU, color="gray", linestyle=":", linewidth=1, label=f"Min limit ({V_MIN_PU} pu)")
        ax.set_title(f"{siting.capitalize()} PV siting")
        ax.set_xlabel("Bus number (1 = near substation, 16 = feeder end)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Voltage (pu)")
    axes[0].legend(fontsize=8)
    plt.suptitle("Midday Feeder Voltage Profiles Across PV Penetration Levels")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "05_voltage_profiles_by_siting.png"), dpi=150)
    plt.close()


if __name__ == "__main__":
    print(f"Feeder total peak load: {total_peak_load_kw():.0f} kW | "
          f"Midday load factor: {MIDDAY_LOAD_FACTOR}\n")

    study_1_baseline_peak()
    print()
    df, summary = study_2_pv_sweep()
    print()
    study_3_voltage_profiles_at_penetrations()

    print("\nAll studies complete. Outputs in outputs/, charts in charts/.")
