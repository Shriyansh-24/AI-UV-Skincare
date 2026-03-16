# ============================================================
# Solara — core/skin_advisor.py
# Burn time calculator + SPF recommendation engine
#
# KEY SCIENCE:
#
# Minimal Erythemal Dose (MED)
#   The minimum UV dose (J/m²) needed to cause visible skin
#   reddening. Varies by Fitzpatrick skin type due to melanin.
#   Source: WHO / CIE standard erythema reference spectrum
#
# Burn Time Formula
#   1 UV Index unit = 0.025 W/m² of UV irradiance
#   Dose rate (J/m²/min) = UV Index × 0.025 × 60 = UV Index × 1.5
#   Burn time (min) = MED ÷ (UV Index × 1.5 × activity multiplier)
#   Source: Diffey B.L. (2002)
#
# SPF (Sun Protection Factor)
#   Multiplies unprotected burn time: Protected = Burn Time × SPF
#
# Activity Multipliers
#   Water reflects 25% extra UV; sweat degrades sunscreen film.
#   Source: WHO Global Solar UV Index guide (2002)
# ============================================================

# MED values (J/m²) per Fitzpatrick type
# Higher melanin content = higher MED = longer time before burning
MED_VALUES = {
    1: 200,    # Very fair — always burns
    2: 250,    # Fair — usually burns
    3: 300,    # Medium — sometimes burns
    4: 450,    # Olive — rarely burns
    5: 600,    # Brown — very rarely burns
    6: 1000,   # Dark — never burns
}

# Activity multipliers and reapplication intervals
# Multiplier > 1.0 means more UV reaches skin (reflection/degradation)
ACTIVITY_MULTIPLIERS = {
    "Casual walk / commute": {"multiplier": 1.0, "note": "Normal UV exposure.",                                              "reapply_hrs": 2.0},
    "Sports / exercise":     {"multiplier": 1.2, "note": "Sweat degrades sunscreen — effective SPF reduced by ~20%.",       "reapply_hrs": 1.5},
    "Beach / swimming":      {"multiplier": 1.4, "note": "Water reflects up to 25% extra UV. Sunscreen washes off rapidly.", "reapply_hrs": 0.75},
    "Gardening":             {"multiplier": 1.1, "note": "Reflected UV from soil and plants adds ~10% exposure.",           "reapply_hrs": 2.0},
    "Just checking":         {"multiplier": 1.0, "note": "Standard UV exposure assumed.",                                   "reapply_hrs": 2.0},
}

# SPF lookup table — rows = UV band, values = (fair, medium, dark) skin groups
# fair = Types I-II, medium = Types III-IV, dark = Types V-VI
SPF_TABLE = {
    "low":       (30, 15, 15),
    "moderate":  (30, 30, 15),
    "high":      (50, 30, 30),
    "very_high": (50, 50, 30),
    "extreme":   (50, 50, 50),
}

def _skin_group(fitzpatrick_id: int) -> str:
    """Maps Fitzpatrick type to skin group for SPF table lookup."""
    if fitzpatrick_id <= 2: return "fair"
    if fitzpatrick_id <= 4: return "medium"
    return "dark"

def _uv_band(uv_index: float) -> str:
    """Maps UV Index to WHO risk band name."""
    if uv_index <= 2:  return "low"
    if uv_index <= 5:  return "moderate"
    if uv_index <= 7:  return "high"
    if uv_index <= 10: return "very_high"
    return "extreme"


# ── Public functions ──────────────────────────────────────────

def calculate_burn_time(uv_index: float, fitzpatrick_id: int, activity: str) -> dict:
    """
    Estimates time to sunburn using the MED formula.

    Returns a dict with burn_time_min and supporting data.
    Returns no_risk=True if UV Index is 0 (e.g. night time).
    """
    # No UV means no burn risk
    if uv_index <= 0:
        return {
            "burn_time_min":       None,
            "med_j_m2":            MED_VALUES.get(fitzpatrick_id, 300),
            "activity_multiplier": 1.0,
            "effective_rate":      0,
            "no_risk":             True,
            "explanation":         "UV Index is 0 — no UV radiation right now.",
        }

    med            = MED_VALUES.get(fitzpatrick_id, 300)
    act            = ACTIVITY_MULTIPLIERS.get(activity, ACTIVITY_MULTIPLIERS["Casual walk / commute"])
    dose_rate      = uv_index * 1.5                # J/m²/min (base rate)
    effective_rate = dose_rate * act["multiplier"] # adjusted for activity
    burn_time      = med / effective_rate

    return {
        "burn_time_min":       round(burn_time),
        "med_j_m2":            med,
        "activity_multiplier": act["multiplier"],
        "dose_rate":           round(dose_rate, 2),
        "effective_rate":      round(effective_rate, 2),
        "no_risk":             False,
        "reapply_hrs":         act["reapply_hrs"],
        "activity_note":       act["note"],
        "explanation": (
            f"MED for Fitzpatrick Type {fitzpatrick_id} = {med} J/m²\n"
            f"UV dose rate = {uv_index} × 1.5 = {dose_rate:.2f} J/m²/min\n"
            f"Activity multiplier ({activity}) = ×{act['multiplier']}\n"
            f"Effective dose rate = {effective_rate:.2f} J/m²/min\n"
            f"Burn time = {med} ÷ {effective_rate:.2f} = {round(burn_time)} minutes"
        ),
    }


def get_spf_recommendation(
    uv_index: float, fitzpatrick_id: int,
    activity: str, duration_hours: float
) -> dict:
    """
    Returns personalised SPF recommendation based on UV, skin type,
    activity, and how long the user plans to be outdoors.
    """
    band      = _uv_band(uv_index)
    group     = _skin_group(fitzpatrick_id)
    group_idx = {"fair": 0, "medium": 1, "dark": 2}[group]
    base_spf  = SPF_TABLE[band][group_idx]

    act         = ACTIVITY_MULTIPLIERS.get(activity, ACTIVITY_MULTIPLIERS["Casual walk / commute"])
    reapply_hrs = act["reapply_hrs"]

    # Bump to SPF 50 for vulnerable skin doing water/sport activities
    final_spf = base_spf
    if activity in ["Beach / swimming", "Sports / exercise"]:
        if fitzpatrick_id <= 3 and base_spf < 50:
            final_spf = 50

    # How many reapplications needed for the planned duration
    reapplications = max(0, int(duration_hours / reapply_hrs) - 1)

    return {
        "recommended_spf":  final_spf,
        "uv_band":          band,
        "skin_group":       group,
        "reapply_hrs":      reapply_hrs,
        "reapplications":   reapplications,
        "activity_note":    act["note"],
        "tips":             _build_tips(uv_index, fitzpatrick_id, activity, duration_hours, final_spf, reapply_hrs),
        "reasoning": (
            f"Skin group: {group.title()} (Type {fitzpatrick_id}) · "
            f"UV band: {band.replace('_', ' ').title()} (UVI {uv_index}) · "
            f"Activity: {activity}"
        ),
    }


def _build_tips(uv_index, fitzpatrick_id, activity, duration_hours, spf, reapply_hrs) -> list:
    """
    Builds a personalised list of protection tips.
    Tips are added conditionally based on UV level, skin type, and activity.
    Each tip has an emoji, a short title, and a detail string.
    """
    tips = []
    reapply_min = int(reapply_hrs * 60)

    # Tip 1 — Apply sunscreen (always shown)
    tips.append({
        "emoji":  "🧴",
        "title":  f"Apply SPF {spf} sunscreen",
        "detail": "Apply generously 20–30 minutes before going outdoors. "
                  "Most people apply only 25–50% of the recommended amount.",
    })

    # Tip 2 — Reapplication schedule (always shown)
    reapply_details = {
        "Beach / swimming":  f"Reapply every {reapply_min} min — water removes sunscreen rapidly. Reapply after every swim.",
        "Sports / exercise": f"Reapply every {reapply_min} min — sweat breaks down the sunscreen film.",
        "Gardening":         f"Reapply every {reapply_min} min — wiping face/hands removes sunscreen.",
    }
    tips.append({
        "emoji":  "🔁",
        "title":  f"Reapply every {reapply_min} minutes",
        "detail": reapply_details.get(activity, f"Reapply every {reapply_min} minutes, especially after sweating."),
    })

    # Tip 3 — Avoid peak hours (UV ≥ moderate)
    if uv_index >= 3:
        tips.append({
            "emoji":  "🕐",
            "title":  "Avoid peak UV hours (10am – 4pm)",
            "detail": "UV peaks at solar noon. UV is typically 60% lower in early morning and late afternoon.",
        })

    # Tip 4 — Protective clothing (high UV or fair skin)
    if uv_index >= 6 or fitzpatrick_id <= 2:
        tips.append({
            "emoji":  "👕",
            "title":  "Wear UV-protective clothing",
            "detail": "UPF 50+ clothing blocks ~98% of UV. Dark, tightly woven fabrics offer the best protection.",
        })

    # Tip 5 — Sunglasses (UV ≥ moderate)
    if uv_index >= 3:
        tips.append({
            "emoji":  "🕶️",
            "title":  "Wear UV400 sunglasses",
            "detail": "UV400 lenses block all wavelengths up to 400nm. Prolonged UV exposure causes cataracts.",
        })

    # Tip 6 — Activity-specific advice
    if activity == "Beach / swimming":
        tips.append({
            "emoji":  "🏊",
            "title":  "Use water-resistant sunscreen",
            "detail": "Standard sunscreen washes off within 40 minutes. Choose water-resistant formula.",
        })
    elif activity == "Sports / exercise":
        tips.append({
            "emoji":  "💧",
            "title":  "Use sweat-resistant sunscreen",
            "detail": "Choose sport formulas labelled sweat-resistant and reapply after heavy sweating.",
        })

    # Tip 7 — Extreme UV warning
    if uv_index >= 8:
        tips.append({
            "emoji":  "⚠️",
            "title":  "Seek shade whenever possible",
            "detail": f"At UV Index {uv_index}, Type I skin can burn in under "
                      f"{max(5, round(200 / (uv_index * 1.5)))} minutes. Shade reduces UV by up to 50%.",
        })

    # Tip 8 — Hydration for long exposure
    if duration_hours >= 2:
        tips.append({
            "emoji":  "💧",
            "title":  "Stay hydrated",
            "detail": "UV + heat increases dehydration. Drink water regularly — dehydration slows skin repair.",
        })

    return tips