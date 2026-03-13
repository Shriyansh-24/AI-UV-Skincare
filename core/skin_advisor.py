# ============================================================
# UV Skincare Advisor — core/skin_advisor.py
# Responsible for: Personalised burn time + SPF advice engine
# Team role: STATISTICIAN's data tables live here
# ============================================================
#
# SCIENCE CONCEPTS IN THIS FILE:
#
#   1. MINIMAL ERYTHEMAL DOSE (MED)
#      The MED is the minimum UV exposure required to cause
#      visible reddening (erythema) on unprotected skin.
#      It is measured in J/m² and varies by skin type.
#      Source: WHO / CIE standard erythema reference action spectrum
#
#   2. BURN TIME FORMULA
#      Time to burn (minutes) = MED / (UV_Index × 0.025 × 60)
#      Where 0.025 W/m² = UV irradiance per 1 UV Index unit
#      Rearranged: Burn Time = MED / (UVI × 1.5)
#      Source: Diffey, B.L. (2002) — UV Index and its application
#
#   3. SPF (SUN PROTECTION FACTOR)
#      SPF extends burn time proportionally:
#      Protected burn time = Unprotected burn time × SPF
#      e.g. SPF 30 means you can stay 30× longer before burning
#
#   4. ACTIVITY MULTIPLIERS
#      Certain activities modify effective UV exposure:
#      - Swimming/water: water reflects 25% extra UV (albedo effect)
#        AND water washes off sunscreen — reapplication needed
#      - Sports/sweat: perspiration degrades sunscreen effectiveness
#      - Sand/beach: sand reflects up to 15% extra UV
#      Source: WHO Global Solar UV Index practical guide (2002)
#
# ============================================================

# ── MED VALUES BY FITZPATRICK TYPE ───────────────────────────
# MED = Minimal Erythemal Dose in J/m²
# These are standard reference values from dermatology literature.
# Your STATISTICIAN should record these in the project data table.
#
# Fitzpatrick Type : MED (J/m²) : Typical characteristics
# ─────────────────────────────────────────────────────────────
#   Type I          :  200       : Always burns, never tans
#   Type II         :  250       : Usually burns, tans minimally
#   Type III        :  300       : Sometimes burns, gradually tans
#   Type IV         :  450       : Rarely burns, tans easily
#   Type V          :  600       : Very rarely burns, tans deeply
#   Type VI         :  1000      : Never burns, deeply pigmented
#
MED_VALUES = {
    1: 200,
    2: 250,
    3: 300,
    4: 450,
    5: 600,
    6: 1000,
}

# ── ACTIVITY UV MULTIPLIERS ───────────────────────────────────
# These multipliers increase effective UV exposure based on
# surface reflectivity (albedo) and sunscreen degradation rate.
#
# activity label (must match sidebar options exactly) : multiplier
#
ACTIVITY_MULTIPLIERS = {
    "Casual walk / commute": {
        "multiplier":  1.0,
        "note":        "Normal UV exposure.",
        "reapply_hrs": 2.0,
    },
    "Sports / exercise": {
        "multiplier":  1.2,
        "note":        "Sweat degrades sunscreen — effective SPF reduced by ~20%.",
        "reapply_hrs": 1.5,
    },
    "Beach / swimming": {
        "multiplier":  1.4,
        "note":        "Water reflects up to 25% extra UV. Sunscreen washes off rapidly.",
        "reapply_hrs": 0.75,   # Reapply every 45 minutes
    },
    "Gardening": {
        "multiplier":  1.1,
        "note":        "Reflected UV from light soil and plants adds ~10% exposure.",
        "reapply_hrs": 2.0,
    },
    "Just checking": {
        "multiplier":  1.0,
        "note":        "Standard UV exposure assumed.",
        "reapply_hrs": 2.0,
    },
}

# ── SPF RECOMMENDATION TABLE ──────────────────────────────────
# Recommended SPF based on UV Index AND Fitzpatrick skin type.
# Rows = UV risk band, Columns = skin type group
#
# Skin type groups:
#   "fair"   = Types I & II   (low melanin, high burn risk)
#   "medium" = Types III & IV (moderate melanin)
#   "dark"   = Types V & VI   (high melanin, natural protection)
#
SPF_TABLE = {
    #  UV band     : (fair,  medium, dark)
    "low":          (30,    15,     15),
    "moderate":     (30,    30,     15),
    "high":         (50,    30,     30),
    "very_high":    (50,    50,     30),
    "extreme":      (50,    50,     50),
}

def _get_skin_group(fitzpatrick_id: int) -> str:
    """Returns skin group string for SPF table lookup."""
    if fitzpatrick_id <= 2:
        return "fair"
    elif fitzpatrick_id <= 4:
        return "medium"
    else:
        return "dark"

def _get_uv_band(uv_index: float) -> str:
    """Returns UV band string for SPF table lookup."""
    if uv_index <= 2:   return "low"
    elif uv_index <= 5: return "moderate"
    elif uv_index <= 7: return "high"
    elif uv_index <= 10:return "very_high"
    else:               return "extreme"


# ══════════════════════════════════════════════════════════════
#  MAIN PUBLIC FUNCTIONS
# ══════════════════════════════════════════════════════════════

def calculate_burn_time(
    uv_index: float,
    fitzpatrick_id: int,
    activity: str
) -> dict:
    """
    Calculates the estimated time to sunburn using the
    standard MED-based formula.

    FORMULA:
        Burn Time (min) = MED / (UVI × 1.5) × (1 / activity_multiplier)

    Derivation:
        - UV irradiance per 1 UVI unit = 0.025 W/m²
        - 1 W/m² for 1 minute = 60 J/m² of UV dose
        - So dose rate (J/m²/min) = UVI × 0.025 × 60 = UVI × 1.5
        - Time = MED / dose_rate = MED / (UVI × 1.5)
        - Activity multiplier increases effective dose rate

    Args:
        uv_index       : current UV Index (float)
        fitzpatrick_id : skin type 1–6
        activity       : activity string matching sidebar options

    Returns:
        dict with burn_time_min, med_value, activity_multiplier,
        dose_rate, and an explanation string for the report
    """

    # Guard: UV Index of 0 means no burn risk
    if uv_index <= 0:
        return {
            "burn_time_min":      None,
            "protected_time_min": None,
            "med_j_m2":           MED_VALUES.get(fitzpatrick_id, 300),
            "activity_multiplier":1.0,
            "dose_rate":          0,
            "no_risk":            True,
            "explanation":        "UV Index is 0 — no UV radiation reaching the surface right now."
        }

    med           = MED_VALUES.get(fitzpatrick_id, 300)
    activity_data = ACTIVITY_MULTIPLIERS.get(activity, ACTIVITY_MULTIPLIERS["Casual walk / commute"])
    multiplier    = activity_data["multiplier"]

    # Core formula
    dose_rate      = uv_index * 1.5          # J/m² per minute
    effective_rate = dose_rate * multiplier  # adjusted for activity
    burn_time      = med / effective_rate    # minutes to sunburn

    return {
        "burn_time_min":       round(burn_time),
        "med_j_m2":            med,
        "activity_multiplier": multiplier,
        "dose_rate":           round(dose_rate, 2),
        "effective_rate":      round(effective_rate, 2),
        "no_risk":             False,
        "reapply_hrs":         activity_data["reapply_hrs"],
        "activity_note":       activity_data["note"],
        "explanation": (
            f"MED for Fitzpatrick Type {fitzpatrick_id} = {med} J/m²\n"
            f"UV dose rate = {uv_index} × 1.5 = {dose_rate:.2f} J/m²/min\n"
            f"Activity multiplier ({activity}) = ×{multiplier}\n"
            f"Effective dose rate = {effective_rate:.2f} J/m²/min\n"
            f"Burn time = {med} ÷ {effective_rate:.2f} = {round(burn_time)} minutes"
        )
    }


def get_spf_recommendation(
    uv_index: float,
    fitzpatrick_id: int,
    activity: str,
    duration_hours: float
) -> dict:
    """
    Returns a personalised SPF recommendation based on:
    - UV Index (current conditions)
    - Fitzpatrick skin type (natural protection level)
    - Activity (sweat/water degrades sunscreen)
    - Duration outdoors (affects how many reapplications needed)

    Args:
        uv_index       : current UV Index
        fitzpatrick_id : skin type 1–6
        activity       : activity string
        duration_hours : planned hours outdoors

    Returns:
        dict with recommended_spf, reapplications, reasoning,
        and a list of protection tips
    """

    uv_band    = _get_uv_band(uv_index)
    skin_group = _get_skin_group(fitzpatrick_id)
    spf_row    = SPF_TABLE[uv_band]

    # Map skin group to table column index
    group_index   = {"fair": 0, "medium": 1, "dark": 2}[skin_group]
    base_spf      = spf_row[group_index]

    # Activity upgrade: bump SPF one level for high-activity outdoors
    activity_data = ACTIVITY_MULTIPLIERS.get(activity, ACTIVITY_MULTIPLIERS["Casual walk / commute"])
    reapply_hrs   = activity_data["reapply_hrs"]

    # Upgrade SPF for water/sport activities on fair skin
    final_spf = base_spf
    if activity in ["Beach / swimming", "Sports / exercise"]:
        if fitzpatrick_id <= 3 and base_spf < 50:
            final_spf = 50   # Bump to max protection for vulnerable skin types

    # Calculate number of reapplications needed
    # First application at time 0, then every reapply_hrs
    reapplications = max(0, int(duration_hours / reapply_hrs) - 1)

    # Build protection tips list based on conditions
    tips = _build_protection_tips(
        uv_index, fitzpatrick_id, activity,
        duration_hours, final_spf, reapply_hrs
    )

    return {
        "recommended_spf":  final_spf,
        "uv_band":          uv_band,
        "skin_group":       skin_group,
        "reapply_hrs":      reapply_hrs,
        "reapplications":   reapplications,
        "activity_note":    activity_data["note"],
        "tips":             tips,
        "reasoning": (
            f"Skin group: {skin_group.title()} (Type {fitzpatrick_id}) · "
            f"UV band: {uv_band.replace('_', ' ').title()} (UVI {uv_index}) · "
            f"Activity: {activity}"
        )
    }


def _build_protection_tips(
    uv_index, fitzpatrick_id, activity,
    duration_hours, spf, reapply_hrs
) -> list:
    """
    Builds a contextual list of protection tips tailored to
    the user's exact situation. Each tip is a dict with
    an emoji, a short title, and a detail string.
    """
    tips = []

    # ── Tip 1: Sunscreen application ─────────────────────────
    tips.append({
        "emoji": "🧴",
        "title": f"Apply SPF {spf} sunscreen",
        "detail": "Apply generously 20–30 minutes before going outdoors. "
                  "Use at least 2mg/cm² — most people apply only 25–50% of the needed amount."
    })

    # ── Tip 2: Reapplication ─────────────────────────────────
    reapply_min = int(reapply_hrs * 60)
    tips.append({
        "emoji": "🔁",
        "title": f"Reapply every {reapply_min} minutes",
        "detail": activity_reapply_detail(activity, reapply_min)
    })

    # ── Tip 3: Peak UV hours warning ─────────────────────────
    if uv_index >= 3:
        tips.append({
            "emoji": "🕐",
            "title": "Avoid peak UV hours (10am – 4pm)",
            "detail": "UV Index peaks at solar noon when the sun is at its highest angle. "
                      "UV is typically 60% lower in early morning and late afternoon."
        })

    # ── Tip 4: Clothing ──────────────────────────────────────
    if uv_index >= 6 or fitzpatrick_id <= 2:
        tips.append({
            "emoji": "👕",
            "title": "Wear UV-protective clothing",
            "detail": "Long-sleeved UPF 50+ clothing blocks ~98% of UV rays. "
                      "Dark, tightly woven fabrics offer better protection than light colours."
        })

    # ── Tip 5: Sunglasses ────────────────────────────────────
    if uv_index >= 3:
        tips.append({
            "emoji": "🕶️",
            "title": "Wear UV400 sunglasses",
            "detail": "UV400 lenses block all wavelengths up to 400nm (both UV-A and UV-B). "
                      "Prolonged UV exposure to eyes can cause cataracts and photokeratitis."
        })

    # ── Tip 6: Activity-specific tips ────────────────────────
    if activity == "Beach / swimming":
        tips.append({
            "emoji": "🏊",
            "title": "Use water-resistant sunscreen",
            "detail": "Standard sunscreen washes off within 40 minutes in water. "
                      "Use water-resistant formula and reapply immediately after towel-drying."
        })
    elif activity == "Sports / exercise":
        tips.append({
            "emoji": "💧",
            "title": "Use sweat-resistant sunscreen",
            "detail": "Perspiration degrades sunscreen film. Choose sport formulas labeled "
                      "'sweat-resistant' and reapply after heavy sweating."
        })

    # ── Tip 7: High UV extreme warning ───────────────────────
    if uv_index >= 8:
        tips.append({
            "emoji": "⚠️",
            "title": "Seek shade whenever possible",
            "detail": f"At UV Index {uv_index}, unprotected skin can begin to burn in under "
                      f"{max(5, round(200 / (uv_index * 1.5)))} minutes (Type I skin). "
                      "A shade umbrella reduces UV exposure by up to 50%."
        })

    # ── Tip 8: Hydration ─────────────────────────────────────
    if duration_hours >= 2:
        tips.append({
            "emoji": "💧",
            "title": "Stay hydrated",
            "detail": "UV exposure combined with heat increases dehydration risk. "
                      "Drink water regularly — dehydration reduces skin's natural repair ability."
        })

    return tips


def activity_reapply_detail(activity: str, reapply_min: int) -> str:
    """Returns a context-specific reapplication tip."""
    details = {
        "Beach / swimming":
            f"Reapply every {reapply_min} min. Water removes sunscreen rapidly — "
            "reapply immediately after each swim, even with water-resistant formula.",
        "Sports / exercise":
            f"Reapply every {reapply_min} min. Sweat breaks down the sunscreen film — "
            "pat dry and reapply during any break in activity.",
        "Gardening":
            f"Reapply every {reapply_min} min. Wiping hands/face on clothing can "
            "remove sunscreen from those areas — check and reapply.",
    }
    return details.get(
        activity,
        f"Reapply every {reapply_min} minutes, especially after sweating or towel drying."
    )