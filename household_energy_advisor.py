"""
Household Energy Requirement Calculator & Advisor
==================================================
An interactive CLI tool that:
  1. Collects household profile, occupancy, appliances, and building envelope data
  2. Estimates gross energy consumption
  3. Applies climate and insulation adjustments
  4. Calculates net grid draw (after solar generation)
  5. Projects monthly electricity bill
  6. Benchmarks against a dataset of 1,000 household profiles
  7. Runs solar ROI analysis for 1, 3, 5, and 10 kWp scenarios
  8. Generates prioritised, quantified energy-saving recommendations

Dataset: household_energy_requirement.csv (1,000 Indian household profiles)
"""

import os
import sys
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & LOOKUP TABLES
# ─────────────────────────────────────────────────────────────────────────────

# Appliance wattages (Watts)
WATTAGE = {
    "ac_per_unit_star": {1: 2000, 2: 1800, 3: 1600, 4: 1400, 5: 1200},
    "ceiling_fan": 75,
    "led_bulb": 10,
    "cfl_bulb": 20,
    "incandescent_bulb": 60,
    "water_heater_electric": 2000,
    "water_heater_solar": 0,         # no grid draw
    "water_heater_heat_pump": 500,
    "water_heater_solar_backup": 600,  # partial grid
    "refrigerator_per_100L": 30,       # base ~30 W per 100 L (5-star); adjusted by rating
    "fridge_star_factor": {1: 1.4, 2: 1.25, 3: 1.1, 4: 1.05, 5: 1.0},
    "microwave": 1000,
    "electric_stove": 1500,
    "dishwasher_per_cycle_kWh": 1.2,   # kWh per cycle (not per hour)
    "washing_machine_front": 500,
    "washing_machine_top": 700,
    "washing_machine_semi": 400,
    "dryer": 2000,
    "tv_32_and_below": 50,
    "tv_33_to_55": 100,
    "tv_above_55": 150,
    "computer": 150,
}

# Climate zone energy adjustment factors
CLIMATE_FACTOR = {
    "Hot & Humid":  1.20,
    "Hot & Dry":    1.15,
    "Composite":    1.05,
    "Temperate":    0.95,
    "Cold":         0.90,
}

# Insulation quality adjustment factors
INSULATION_FACTOR = {
    "Excellent": 0.90,
    "Good":      1.00,
    "Average":   1.10,
    "Poor":      1.25,
}

# Peak sun hours by climate zone (hours/day)
PEAK_SUN_HOURS = {
    "Hot & Humid":  4.5,
    "Hot & Dry":    5.5,
    "Composite":    5.0,
    "Temperate":    4.0,
    "Cold":         3.5,
}

# Electricity tariff by city tier (₹/kWh) — approximate slab averages
TARIFF = {
    "Tier 1": 7.50,
    "Tier 2": 6.50,
    "Tier 3": 5.50,
}

# Solar installation cost (₹/kWp) — approximate market rate
SOLAR_COST_PER_KWP = 65_000

# Solar scenarios to evaluate
SOLAR_SCENARIOS_KWP = [1, 3, 5, 10]

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def hr(char="─", width=72):
    print(char * width)

def section(title):
    print()
    hr("═")
    print(f"  {title}")
    hr("═")

def ask_int(prompt, default=None, min_val=0, max_val=9999):
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"  {prompt}{suffix}: ").strip()
        if raw == "" and default is not None:
            return default
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"    ⚠  Please enter a value between {min_val} and {max_val}.")
        except ValueError:
            print("    ⚠  Please enter a whole number.")

def ask_float(prompt, default=None, min_val=0.0, max_val=24.0):
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"  {prompt}{suffix}: ").strip()
        if raw == "" and default is not None:
            return default
        try:
            val = float(raw)
            if min_val <= val <= max_val:
                return val
            print(f"    ⚠  Please enter a value between {min_val} and {max_val}.")
        except ValueError:
            print("    ⚠  Please enter a valid number.")

def ask_choice(prompt, choices):
    """Display numbered menu and return the chosen string."""
    while True:
        print(f"  {prompt}")
        for i, c in enumerate(choices, 1):
            print(f"    {i}. {c}")
        raw = input("  Enter number: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print("    ⚠  Invalid selection.")

def ask_yes_no(prompt, default=None):
    hint = " [y/n]"
    if default is True:
        hint = " [Y/n]"
    elif default is False:
        hint = " [y/N]"
    while True:
        raw = input(f"  {prompt}{hint}: ").strip().lower()
        if raw == "" and default is not None:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("    ⚠  Please enter y or n.")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — COLLECT HOUSEHOLD PROFILE
# ─────────────────────────────────────────────────────────────────────────────

def collect_profile():
    section("STEP 1 — Household Profile")
    house_type = ask_choice("House type:", [
        "Apartment", "Row House", "Independent House", "Villa", "Studio"
    ])
    floor_area = ask_int("Floor area (sq ft)", default=1000, min_val=100, max_val=20000)
    num_bedrooms = ask_int("Number of bedrooms", default=2, min_val=1, max_val=20)
    num_floors = ask_int("Number of floors", default=1, min_val=1, max_val=50)

    climate_zone = ask_choice("Climate zone:", list(CLIMATE_FACTOR.keys()))
    city_tier = ask_choice("City tier:", ["Tier 1", "Tier 2", "Tier 3"])

    return {
        "house_type": house_type,
        "floor_area_sqft": floor_area,
        "num_bedrooms": num_bedrooms,
        "num_floors": num_floors,
        "climate_zone": climate_zone,
        "city_tier": city_tier,
    }

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — OCCUPANCY
# ─────────────────────────────────────────────────────────────────────────────

def collect_occupancy():
    section("STEP 2 — Occupancy Details")
    num_adults = ask_int("Number of adults", default=2, min_val=1, max_val=20)
    num_children = ask_int("Number of children", default=0, min_val=0, max_val=20)
    return {
        "num_adults": num_adults,
        "num_children": num_children,
        "num_occupants": num_adults + num_children,
    }

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — APPLIANCE INVENTORY
# ─────────────────────────────────────────────────────────────────────────────

def collect_appliances():
    section("STEP 3 — Appliance Inventory")

    # Air Conditioners
    print("\n  — Air Conditioning —")
    has_ac = ask_yes_no("Do you have air conditioner(s)?", default=False)
    num_ac = ac_star = ac_hrs = 0
    if has_ac:
        num_ac = ask_int("Number of AC units", default=1, min_val=1, max_val=20)
        ac_star = ask_int("AC star rating (1–5)", default=3, min_val=1, max_val=5)
        ac_hrs = ask_float("Average AC usage hours per day", default=6.0)

    # Fans
    print("\n  — Fans & Lighting —")
    num_fans = ask_int("Number of ceiling fans", default=3, min_val=0, max_val=50)
    num_led = ask_int("Number of LED bulbs", default=10, min_val=0, max_val=200)
    num_cfl = ask_int("Number of CFL bulbs", default=2, min_val=0, max_val=200)
    num_incandescent = ask_int("Number of incandescent bulbs", default=0, min_val=0, max_val=200)
    lighting_hrs = ask_float("Average lighting usage hours per day", default=6.0)

    # Water Heater
    print("\n  — Water Heating —")
    water_heater_type = ask_choice("Water heater type:", [
        "Electric", "Solar", "Solar + Backup", "Heat Pump", "None"
    ])
    water_heater_capacity = water_heater_hrs = 0
    if water_heater_type != "None":
        water_heater_capacity = ask_int("Water heater capacity (litres)", default=15, min_val=5, max_val=500)
        water_heater_hrs = ask_float("Water heater usage hours per day", default=1.0)

    # Kitchen & Laundry
    print("\n  — Kitchen & Laundry —")
    has_fridge = ask_yes_no("Do you have a refrigerator?", default=True)
    fridge_capacity = fridge_star = 0
    if has_fridge:
        fridge_capacity = ask_int("Refrigerator capacity (litres)", default=250, min_val=50, max_val=1000)
        fridge_star = ask_int("Refrigerator star rating (1–5)", default=3, min_val=1, max_val=5)

    has_microwave = ask_yes_no("Do you have a microwave?", default=False)
    has_electric_stove = ask_yes_no("Do you have an electric stove?", default=False)

    has_dishwasher = ask_yes_no("Do you have a dishwasher?", default=False)
    dishwasher_cycles = 0
    if has_dishwasher:
        dishwasher_cycles = ask_int("Dishwasher cycles per week", default=7, min_val=1, max_val=21)

    has_washing_machine = ask_yes_no("Do you have a washing machine?", default=True)
    washing_machine_type = "None"
    washing_cycles = 0
    if has_washing_machine:
        washing_machine_type = ask_choice("Washing machine type:", [
            "Front Load", "Top Load", "Semi-Automatic"
        ])
        washing_cycles = ask_int("Washing cycles per week", default=4, min_val=1, max_val=21)

    has_dryer = ask_yes_no("Do you have a clothes dryer?", default=False)

    # Entertainment & Computers
    print("\n  — Entertainment & Computing —")
    num_tvs = ask_int("Number of TVs", default=1, min_val=0, max_val=20)
    tv_size = tv_hrs = 0
    if num_tvs > 0:
        tv_size = ask_int("Average TV screen size (inches)", default=43, min_val=10, max_val=100)
        tv_hrs = ask_float("Average TV usage hours per day", default=5.0)

    num_computers = ask_int("Number of computers / laptops", default=1, min_val=0, max_val=20)
    computer_hrs = 0
    if num_computers > 0:
        computer_hrs = ask_float("Average computer usage hours per day", default=4.0)

    return {
        "has_ac": int(has_ac),
        "num_ac_units": num_ac,
        "ac_star_rating": ac_star,
        "ac_usage_hrs_per_day": ac_hrs,
        "num_ceiling_fans": num_fans,
        "num_led_bulbs": num_led,
        "num_cfl_bulbs": num_cfl,
        "num_incandescent_bulbs": num_incandescent,
        "avg_lighting_hrs_per_day": lighting_hrs,
        "water_heater_type": water_heater_type,
        "water_heater_capacity_L": water_heater_capacity,
        "water_heater_usage_hrs_per_day": water_heater_hrs,
        "has_refrigerator": int(has_fridge),
        "fridge_capacity_L": fridge_capacity,
        "fridge_star_rating": fridge_star,
        "has_microwave": int(has_microwave),
        "has_electric_stove": int(has_electric_stove),
        "has_dishwasher": int(has_dishwasher),
        "dishwasher_cycles_per_week": dishwasher_cycles,
        "has_washing_machine": int(has_washing_machine),
        "washing_machine_type": washing_machine_type,
        "washing_cycles_per_week": washing_cycles,
        "has_dryer": int(has_dryer),
        "num_tvs": num_tvs,
        "tv_screen_size_inch": tv_size,
        "tv_usage_hrs_per_day": tv_hrs,
        "num_computers": num_computers,
        "computer_usage_hrs_per_day": computer_hrs,
    }

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — BUILDING ENVELOPE
# ─────────────────────────────────────────────────────────────────────────────

def collect_building_envelope():
    section("STEP 4 — Building Envelope")
    insulation = ask_choice("Insulation quality:", list(INSULATION_FACTOR.keys()))
    window_type = ask_choice("Window type:", [
        "Single Pane", "Double Pane", "Triple Pane", "No Windows"
    ])
    roof_type = ask_choice("Roof type:", [
        "Flat RCC", "Sloped Tiled", "Green Roof", "Metal Sheet", "Other"
    ])
    return {
        "insulation_quality": insulation,
        "window_type": window_type,
        "roof_type": roof_type,
    }

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — RENEWABLE ENERGY ASSETS
# ─────────────────────────────────────────────────────────────────────────────

def collect_renewables():
    section("STEP 5 — Renewable Energy Assets")
    has_solar = ask_yes_no("Do you have rooftop solar panels?", default=False)
    solar_capacity = 0
    if has_solar:
        solar_capacity = ask_float("Solar panel capacity (kWp)", default=3.0, max_val=100)

    has_battery = ask_yes_no("Do you have battery storage?", default=False)
    battery_capacity = 0
    if has_battery:
        battery_capacity = ask_float("Battery storage capacity (kWh)", default=5.0, max_val=200)

    return {
        "has_solar_panels": int(has_solar),
        "solar_capacity_kWp": solar_capacity,
        "has_battery_storage": int(has_battery),
        "battery_capacity_kWh": battery_capacity,
    }

# ─────────────────────────────────────────────────────────────────────────────
# ENERGY CALCULATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def calculate_appliance_consumption(ap):
    """
    Returns a dict: appliance_name -> daily_kWh
    """
    daily = {}

    # Air conditioning
    if ap["has_ac"] and ap["num_ac_units"] > 0:
        watt = WATTAGE["ac_per_unit_star"].get(ap["ac_star_rating"], 1600)
        daily["Air Conditioning"] = (
            ap["num_ac_units"] * watt * ap["ac_usage_hrs_per_day"] / 1000
        )

    # Ceiling fans
    if ap["num_ceiling_fans"] > 0:
        daily["Ceiling Fans"] = (
            ap["num_ceiling_fans"] * WATTAGE["ceiling_fan"] * ap["avg_lighting_hrs_per_day"] / 1000
        )

    # Lighting
    lighting_kWh = (
        ap["num_led_bulbs"] * WATTAGE["led_bulb"] +
        ap["num_cfl_bulbs"] * WATTAGE["cfl_bulb"] +
        ap["num_incandescent_bulbs"] * WATTAGE["incandescent_bulb"]
    ) * ap["avg_lighting_hrs_per_day"] / 1000
    if lighting_kWh > 0:
        daily["Lighting"] = lighting_kWh

    # Water heater
    wh_type = ap["water_heater_type"]
    if wh_type == "Electric":
        wh_w = WATTAGE["water_heater_electric"]
    elif wh_type == "Solar":
        wh_w = WATTAGE["water_heater_solar"]
    elif wh_type in ("Solar + Backup",):
        wh_w = WATTAGE["water_heater_solar_backup"]
    elif wh_type == "Heat Pump":
        wh_w = WATTAGE["water_heater_heat_pump"]
    else:
        wh_w = 0
    wh_kwh = wh_w * ap["water_heater_usage_hrs_per_day"] / 1000
    if wh_kwh > 0:
        daily["Water Heater"] = wh_kwh

    # Refrigerator (runs ~24 h, but duty cycle ~35%)
    if ap["has_refrigerator"] and ap["fridge_capacity_L"] > 0:
        base_w = (ap["fridge_capacity_L"] / 100) * WATTAGE["refrigerator_per_100L"]
        star_f = WATTAGE["fridge_star_factor"].get(ap["fridge_star_rating"], 1.0)
        daily["Refrigerator"] = base_w * star_f * 24 * 0.35 / 1000

    # Microwave (~1 h/day assumed)
    if ap["has_microwave"]:
        daily["Microwave"] = WATTAGE["microwave"] * 1.0 / 1000

    # Electric stove (~2 h/day assumed)
    if ap["has_electric_stove"]:
        daily["Electric Stove"] = WATTAGE["electric_stove"] * 2.0 / 1000

    # Dishwasher (cycles/week → daily equivalent)
    if ap["has_dishwasher"] and ap["dishwasher_cycles_per_week"] > 0:
        daily["Dishwasher"] = (
            ap["dishwasher_cycles_per_week"] * WATTAGE["dishwasher_per_cycle_kWh"] / 7
        )

    # Washing machine
    if ap["has_washing_machine"] and ap["washing_cycles_per_week"] > 0:
        wm_type = ap["washing_machine_type"]
        if wm_type == "Front Load":
            wm_w = WATTAGE["washing_machine_front"]
        elif wm_type == "Semi-Automatic":
            wm_w = WATTAGE["washing_machine_semi"]
        else:
            wm_w = WATTAGE["washing_machine_top"]
        # 1 h per cycle assumed
        daily["Washing Machine"] = wm_w * ap["washing_cycles_per_week"] / 7 / 1000

    # Dryer (1 h per wash cycle)
    if ap["has_dryer"] and ap.get("washing_cycles_per_week", 0) > 0:
        daily["Dryer"] = WATTAGE["dryer"] * ap["washing_cycles_per_week"] / 7 / 1000

    # TVs
    if ap["num_tvs"] > 0 and ap["tv_usage_hrs_per_day"] > 0:
        sz = ap["tv_screen_size_inch"]
        if sz <= 32:
            tv_w = WATTAGE["tv_32_and_below"]
        elif sz <= 55:
            tv_w = WATTAGE["tv_33_to_55"]
        else:
            tv_w = WATTAGE["tv_above_55"]
        daily["Television(s)"] = ap["num_tvs"] * tv_w * ap["tv_usage_hrs_per_day"] / 1000

    # Computers
    if ap["num_computers"] > 0 and ap["computer_usage_hrs_per_day"] > 0:
        daily["Computers/Laptops"] = (
            ap["num_computers"] * WATTAGE["computer"] * ap["computer_usage_hrs_per_day"] / 1000
        )

    return daily


def compute_energy(profile, appliances, building, renewables):
    """
    Returns the full energy computation result dict.
    """
    # Step 1: Gross daily kWh (appliance sum)
    appliance_breakdown = calculate_appliance_consumption(appliances)
    gross_daily_kwh = sum(appliance_breakdown.values())

    # Step 2: Climate & insulation adjustments
    climate_f = CLIMATE_FACTOR.get(profile["climate_zone"], 1.0)
    insulation_f = INSULATION_FACTOR.get(building["insulation_quality"], 1.0)
    adjusted_daily_kwh = gross_daily_kwh * climate_f * insulation_f

    # Step 3: Solar generation
    peak_sun = PEAK_SUN_HOURS.get(profile["climate_zone"], 4.5)
    solar_gen_daily = renewables["solar_capacity_kWp"] * peak_sun if renewables["has_solar_panels"] else 0

    # Step 4: Net grid draw
    net_daily_kwh = max(0, adjusted_daily_kwh - solar_gen_daily)

    # Step 5: Monthly bill
    tariff = TARIFF.get(profile["city_tier"], 6.5)
    monthly_kwh = net_daily_kwh * 30
    monthly_bill = monthly_kwh * tariff

    return {
        "appliance_breakdown": appliance_breakdown,
        "gross_daily_kwh": gross_daily_kwh,
        "climate_factor": climate_f,
        "insulation_factor": insulation_f,
        "adjusted_daily_kwh": adjusted_daily_kwh,
        "solar_gen_daily_kwh": solar_gen_daily,
        "net_daily_kwh": net_daily_kwh,
        "net_monthly_kwh": monthly_kwh,
        "tariff_per_kwh": tariff,
        "monthly_bill_inr": monthly_bill,
    }

# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARKING
# ─────────────────────────────────────────────────────────────────────────────

def benchmark(profile, energy_result, df):
    """
    Compare household against similar peers in the dataset.
    """
    peers = df[
        (df["house_type"] == profile["house_type"]) &
        (df["climate_zone"] == profile["climate_zone"]) &
        (df["num_bedrooms"] == profile["num_bedrooms"])
    ]

    # Fallback: relax bedrooms filter
    if len(peers) < 5:
        peers = df[
            (df["house_type"] == profile["house_type"]) &
            (df["climate_zone"] == profile["climate_zone"])
        ]

    # Final fallback: climate zone only
    if len(peers) < 5:
        peers = df[df["climate_zone"] == profile["climate_zone"]]

    peer_avg = peers["daily_energy_consumption_kWh"].mean()
    peer_p25 = peers["daily_energy_consumption_kWh"].quantile(0.25)
    peer_p75 = peers["daily_energy_consumption_kWh"].quantile(0.75)

    user_daily = energy_result["adjusted_daily_kwh"]
    pct_vs_avg = ((user_daily - peer_avg) / peer_avg) * 100

    return {
        "peer_count": len(peers),
        "peer_avg_daily_kwh": peer_avg,
        "peer_p25_daily_kwh": peer_p25,
        "peer_p75_daily_kwh": peer_p75,
        "pct_vs_avg": pct_vs_avg,
    }

# ─────────────────────────────────────────────────────────────────────────────
# SOLAR ROI ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def solar_roi_analysis(profile, energy_result):
    """
    Evaluate 1, 3, 5, and 10 kWp scenarios.
    Returns list of scenario dicts.
    """
    peak_sun = PEAK_SUN_HOURS[profile["climate_zone"]]
    tariff = energy_result["tariff_per_kwh"]
    annual_consumption = energy_result["adjusted_daily_kwh"] * 365
    results = []

    for kWp in SOLAR_SCENARIOS_KWP:
        annual_gen = kWp * peak_sun * 365        # kWh/year
        annual_offset = min(annual_gen, annual_consumption)
        annual_savings = annual_offset * tariff
        capital_cost = kWp * SOLAR_COST_PER_KWP
        payback_years = capital_cost / annual_savings if annual_savings > 0 else float("inf")
        net_savings_25yr = annual_savings * 25 - capital_cost
        co2_offset_tpa = annual_offset * 0.82 / 1000  # tonne CO₂/year (India grid factor ~0.82 kg/kWh)

        results.append({
            "kWp": kWp,
            "annual_gen_kWh": annual_gen,
            "annual_savings_inr": annual_savings,
            "capital_cost_inr": capital_cost,
            "payback_years": payback_years,
            "net_savings_25yr_inr": net_savings_25yr,
            "co2_offset_tpa": co2_offset_tpa,
        })

    return results

# ─────────────────────────────────────────────────────────────────────────────
# RECOMMENDATIONS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def generate_recommendations(appliances, building, profile, energy_result):
    """
    Returns a list of (priority, title, estimated_saving_kWh_per_month, description).
    """
    recs = []
    tariff = energy_result["tariff_per_kwh"]
    monthly = energy_result["net_monthly_kwh"]

    # 1. Switch incandescent bulbs to LED
    if appliances["num_incandescent_bulbs"] > 0:
        saving_kwh = (
            appliances["num_incandescent_bulbs"]
            * (WATTAGE["incandescent_bulb"] - WATTAGE["led_bulb"])
            * appliances["avg_lighting_hrs_per_day"]
            * 30 / 1000
        )
        saving_inr = saving_kwh * tariff
        recs.append((
            1,
            f"Replace {appliances['num_incandescent_bulbs']} incandescent bulb(s) with LEDs",
            saving_kwh,
            f"Saves ≈{saving_kwh:.1f} kWh/month (₹{saving_inr:.0f}/month). "
            "LEDs use ~85% less electricity and last 15× longer."
        ))

    # 2. AC thermostat optimisation (raise set-point by 2 °C)
    if appliances["has_ac"] and appliances["num_ac_units"] > 0:
        # Each 1 °C raise ≈ 6% saving on AC load
        ac_monthly = energy_result["appliance_breakdown"].get("Air Conditioning", 0) * 30
        saving_kwh = ac_monthly * 0.12  # 2 °C → ~12%
        saving_inr = saving_kwh * tariff
        recs.append((
            2,
            "Set AC thermostat to 24–26 °C (raise by 2 °C)",
            saving_kwh,
            f"Saves ≈{saving_kwh:.1f} kWh/month (₹{saving_inr:.0f}/month). "
            "Every degree above 18 °C reduces AC energy by ~6%."
        ))

    # 3. Poor/average insulation improvement
    if building["insulation_quality"] in ("Poor", "Average"):
        saving_factor = 0.10 if building["insulation_quality"] == "Average" else 0.20
        saving_kwh = monthly * saving_factor
        saving_inr = saving_kwh * tariff
        recs.append((
            3,
            f"Improve insulation (currently: {building['insulation_quality']})",
            saving_kwh,
            f"Saves ≈{saving_kwh:.1f} kWh/month (₹{saving_inr:.0f}/month). "
            "Good insulation reduces heating/cooling load significantly."
        ))

    # 4. Switch electric water heater to solar
    if appliances["water_heater_type"] == "Electric":
        saving_kwh = energy_result["appliance_breakdown"].get("Water Heater", 0) * 30 * 0.80
        saving_inr = saving_kwh * tariff
        recs.append((
            4,
            "Replace electric water heater with solar water heater",
            saving_kwh,
            f"Saves ≈{saving_kwh:.1f} kWh/month (₹{saving_inr:.0f}/month). "
            "Solar water heaters cover ~80–90% of daily hot water needs using free solar energy."
        ))

    # 5. Install rooftop solar if not present
    if not appliances.get("has_solar_panels", False) and not appliances.get("has_solar", False):
        # check renewables flag
        pass  # handled in solar ROI section

    # 6. Upgrade low star-rated refrigerator
    if appliances["has_refrigerator"] and appliances["fridge_star_rating"] <= 2:
        current_kwh = energy_result["appliance_breakdown"].get("Refrigerator", 0) * 30
        saving_kwh = current_kwh * 0.30
        saving_inr = saving_kwh * tariff
        recs.append((
            5,
            f"Upgrade refrigerator to 5-star model (current: {appliances['fridge_star_rating']}-star)",
            saving_kwh,
            f"Saves ≈{saving_kwh:.1f} kWh/month (₹{saving_inr:.0f}/month). "
            "A 5-star fridge uses ~30–40% less energy than a 2-star model."
        ))

    # 7. Upgrade low-star AC
    if appliances["has_ac"] and appliances["ac_star_rating"] <= 2:
        ac_monthly = energy_result["appliance_breakdown"].get("Air Conditioning", 0) * 30
        saving_kwh = ac_monthly * 0.25
        saving_inr = saving_kwh * tariff
        recs.append((
            6,
            f"Upgrade AC to 5-star inverter model (current: {appliances['ac_star_rating']}-star)",
            saving_kwh,
            f"Saves ≈{saving_kwh:.1f} kWh/month (₹{saving_inr:.0f}/month). "
            "5-star inverter ACs use 25–40% less electricity."
        ))

    # Sort by saving (descending) and re-number priority
    recs.sort(key=lambda x: -x[2])
    return [(i + 1,) + r[1:] for i, r in enumerate(recs)]

# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY RESULTS
# ─────────────────────────────────────────────────────────────────────────────

def display_results(profile, appliances, building, renewables, energy, bench, solar_scenarios, recs):
    section("ENERGY CONSUMPTION REPORT")

    print(f"\n  Household:  {profile['house_type']} | {profile['num_bedrooms']} BHK | "
          f"{profile['floor_area_sqft']} sq ft | {profile['num_floors']} floor(s)")
    print(f"  Location:   {profile['city_tier']}, {profile['climate_zone']} zone")
    print(f"  Occupants:  {appliances.get('num_occupants',0)} "
          f"({appliances.get('num_adults',0)} adults + {appliances.get('num_children',0)} children)")

    # Appliance breakdown
    print("\n  ┌─────────────────────────────────────────────────┐")
    print("  │         APPLIANCE-LEVEL DAILY CONSUMPTION       │")
    print("  ├───────────────────────────────────┬─────────────┤")
    print("  │ Appliance                         │  kWh / day  │")
    print("  ├───────────────────────────────────┼─────────────┤")
    for name, kwh in sorted(energy["appliance_breakdown"].items(), key=lambda x: -x[1]):
        print(f"  │ {name:<35} │  {kwh:>7.3f}    │")
    print("  ├───────────────────────────────────┼─────────────┤")
    print(f"  │ {'GROSS TOTAL':<35} │  {energy['gross_daily_kwh']:>7.3f}    │")
    print("  └───────────────────────────────────┴─────────────┘")

    # Adjustment factors
    print(f"\n  Climate factor  ({profile['climate_zone']:>15}):  × {energy['climate_factor']:.2f}")
    print(f"  Insulation factor ({building['insulation_quality']:>12}):  × {energy['insulation_factor']:.2f}")
    print(f"  Adjusted daily consumption            :  {energy['adjusted_daily_kwh']:.2f} kWh/day")

    if renewables["has_solar_panels"]:
        print(f"  Solar generation ({renewables['solar_capacity_kWp']} kWp):  −{energy['solar_gen_daily_kwh']:.2f} kWh/day")

    hr()
    print(f"  Net grid draw      :  {energy['net_daily_kwh']:.2f} kWh/day")
    print(f"  Net monthly usage  :  {energy['net_monthly_kwh']:.1f} kWh/month")
    print(f"  Tariff             :  ₹{energy['tariff_per_kwh']:.2f}/kWh")
    print(f"  ► Estimated monthly bill: ₹{energy['monthly_bill_inr']:.0f}")
    hr()

    # Benchmarking
    section("BENCHMARKING vs SIMILAR HOUSEHOLDS")
    b = bench
    user_daily = energy["adjusted_daily_kwh"]
    cmp_label = "ABOVE" if b["pct_vs_avg"] > 0 else "BELOW"
    print(f"\n  Peer group:  {b['peer_count']} similar households "
          f"({profile['house_type']}, {profile['climate_zone']}, {profile['num_bedrooms']} BHK)")
    print(f"  Peer avg daily consumption : {b['peer_avg_daily_kwh']:.2f} kWh")
    print(f"  Peer 25th–75th percentile  : {b['peer_p25_daily_kwh']:.2f} – {b['peer_p75_daily_kwh']:.2f} kWh")
    print(f"  Your daily consumption     : {user_daily:.2f} kWh")
    print(f"  ► You are {abs(b['pct_vs_avg']):.1f}% {cmp_label} the peer average.")

    if user_daily <= b["peer_p25_daily_kwh"]:
        print("  ✅ Excellent! You are in the most efficient 25% of similar homes.")
    elif user_daily <= b["peer_avg_daily_kwh"]:
        print("  ✅ Good. You are below average for similar homes.")
    elif user_daily <= b["peer_p75_daily_kwh"]:
        print("  ⚠  You are above average but within typical range. Improvements possible.")
    else:
        print("  🔴 You are in the top-consuming 25% of similar homes. Action recommended.")

    # Solar ROI
    section("SOLAR ROI ANALYSIS")
    print(f"\n  Location: {profile['climate_zone']} (≈{PEAK_SUN_HOURS[profile['climate_zone']]} peak sun hours/day)")
    print()
    print(f"  {'Capacity':>10} | {'Annual Gen':>12} | {'Annual Saving':>14} | "
          f"{'Capital Cost':>13} | {'Payback':>9} | {'25-yr Net':>12} | {'CO₂ Offset':>12}")
    print(f"  {'(kWp)':>10} | {'(kWh/yr)':>12} | {'(₹/yr)':>14} | "
          f"{'(₹)':>13} | {'(years)':>9} | {'Saving (₹)':>12} | {'(tonnes/yr)':>12}")
    hr("─", 115)
    for s in solar_scenarios:
        pb = f"{s['payback_years']:.1f}" if s['payback_years'] != float("inf") else "N/A"
        print(f"  {s['kWp']:>10} kWp | {s['annual_gen_kWh']:>10,.0f}   | "
              f"  ₹{s['annual_savings_inr']:>10,.0f}   | "
              f"   ₹{s['capital_cost_inr']:>9,.0f}   | {pb:>9} | "
              f"   ₹{s['net_savings_25yr_inr']:>8,.0f}   | {s['co2_offset_tpa']:>11.2f}")

    # Recommendations
    section("ENERGY-SAVING RECOMMENDATIONS (Prioritised)")
    if not recs:
        print("\n  🎉 No major improvements identified — your setup is already well-optimised!")
    else:
        total_potential_saving = sum(r[2] for r in recs)
        print(f"\n  Total potential saving: ≈{total_potential_saving:.1f} kWh/month "
              f"(₹{total_potential_saving * energy['tariff_per_kwh']:.0f}/month)\n")
        for priority, title, saving_kwh, desc in recs:
            print(f"  [{priority}] {title}")
            print(f"      {desc}")
            print()

    print()
    hr("═")
    print("  Thank you for using the Household Energy Requirement Calculator & Advisor!")
    print("  For professional energy audits, contact your local DISCOM or a BEE-certified auditor.")
    hr("═")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset():
    """Load the benchmark dataset, trying known paths."""
    candidate_paths = [
        "household_energy_requirement.csv",
        os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else ".", "household_energy_requirement.csv"),
        "/mnt/user-data/uploads/household_energy_requirement.csv",
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                return pd.read_csv(path)
            except Exception:
                pass
    print("\n  ⚠  WARNING: Could not load benchmark dataset. Benchmarking will be skipped.")
    return None


def main():
    print()
    hr("═")
    print("       HOUSEHOLD ENERGY REQUIREMENT CALCULATOR & ADVISOR")
    print("               Personalised Energy Intelligence for India")
    hr("═")
    print()
    print("  This tool will guide you through 5 short sections to estimate your")
    print("  household electricity consumption, benchmark it against peers, analyse")
    print("  solar options, and give you actionable saving recommendations.")
    print()
    print("  Press Ctrl+C at any time to exit.")
    print()

    df = load_dataset()

    try:
        profile   = collect_profile()
        occupancy = collect_occupancy()
        appliances_raw = collect_appliances()
        building  = collect_building_envelope()
        renewables = collect_renewables()
    except KeyboardInterrupt:
        print("\n\n  Exited by user.")
        sys.exit(0)

    # Merge occupancy into appliances for convenience
    appliances = {**occupancy, **appliances_raw}

    # Compute energy
    energy = compute_energy(profile, appliances, building, renewables)

    # Benchmark
    if df is not None:
        bench = benchmark(profile, energy, df)
    else:
        bench = {
            "peer_count": 0,
            "peer_avg_daily_kwh": 0,
            "peer_p25_daily_kwh": 0,
            "peer_p75_daily_kwh": 0,
            "pct_vs_avg": 0,
        }

    # Solar ROI
    solar_scenarios = solar_roi_analysis(profile, energy)

    # Recommendations
    recs = generate_recommendations(appliances, building, profile, energy)

    # Display
    display_results(profile, appliances, building, renewables,
                    energy, bench, solar_scenarios, recs)


if __name__ == "__main__":
    main()