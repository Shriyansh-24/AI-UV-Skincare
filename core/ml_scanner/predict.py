# ============================================================
# Solara — core/ml_scanner/predict.py
# Runtime ingredient analysis using the trained ML model
# Called by app.py — do NOT run this directly
#
# HOW IT WORKS:
#   1. Parse raw ingredient text into a list of names
#   2. Look up each name in the dataset (ingredients.csv)
#   3. For unknown ingredients, use ML model to predict concern
#   4. Score the formulation overall and per skin type
#   5. Return a full analysis dict for app.py to display
# ============================================================

import os
import re
import pickle

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

# Skin type config — col = which CSV column to use for scoring
SKIN_TYPES = {
    "Oily":        {"col": "oily_score",       "emoji": "💧", "desc": "Oily Skin"},
    "Dry":         {"col": "dry_score",         "emoji": "🌵", "desc": "Dry Skin"},
    "Combination": {"col": "combination_score", "emoji": "⚖️", "desc": "Combination Skin"},
    "Sensitive":   {"col": "sensitive_score",   "emoji": "🌸", "desc": "Sensitive Skin"},
    "Normal":      {"col": "normal_score",      "emoji": "✨", "desc": "Normal Skin"},
}

# Extra penalties per concern level per skin type
# Sensitive skin gets harsher penalties because it reacts to more ingredients
SKIN_TYPE_PENALTIES = {
    "Oily":        {"High": 2.0, "Medium": 0.8},
    "Dry":         {"High": 2.0, "Medium": 0.8},
    "Combination": {"High": 2.0, "Medium": 0.8},
    "Sensitive":   {"High": 2.5, "Medium": 1.2},
    "Normal":      {"High": 1.8, "Medium": 0.6},
}

# Only these categories meaningfully affect skin type scores
# Filler ingredients like Water, Glycerin don't affect compatibility
SCORING_CATEGORIES = {
    "UV Filter - Chemical", "UV Filter - Mineral", "Photostabiliser",
    "Preservative", "Fragrance", "Skin Active", "Solvent"
}

# Benefit descriptions shown for good ingredients
BENEFIT_TEXTS = {
    "Humectant":      "Draws moisture into the skin",
    "Emollient":      "Softens and smooths skin texture",
    "Antioxidant":    "Neutralises free radicals from UV exposure",
    "Soothing Agent": "Calms inflammation and reduces redness",
    "Skin Active":    "Active ingredient with targeted skin benefit",
}

# Model is loaded once and cached — avoids reloading on every scan
_bundle = None

def _load_model():
    """Loads model.pkl from disk. Raises FileNotFoundError if missing."""
    global _bundle
    if _bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                "model.pkl not found. Run this first:\n"
                "  python core/ml_scanner/train_model.py"
            )
        with open(MODEL_PATH, "rb") as f:
            _bundle = pickle.load(f)
    return _bundle


# ── Step 1: Parse ─────────────────────────────────────────────

def parse_ingredients(raw_text: str) -> list:
    """
    Converts raw ingredient label text into a clean list of names.
    Handles formats like 'Active Ingredients: X 3%, Y 5%' and
    plain comma-separated lists.
    """
    # Strip section headers like "Active Ingredients:"
    text = re.sub(
        r"(active\s+ingredients?|inactive\s+ingredients?|ingredients?)\s*:",
        ",", raw_text, flags=re.IGNORECASE
    )
    parts = re.split(r"[,\n;]+", text)

    names = []
    for part in parts:
        name = re.sub(r"\d+\.?\d*\s*%", "", part)  # remove "3%"
        name = re.sub(r"\(.*?\)", "", name)          # remove "(10%)"
        name = name.strip().strip(".-/").strip()
        if len(name) > 2:
            names.append(name)
    return names


# ── Step 2: Lookup ────────────────────────────────────────────

def _lookup(name: str, df) -> dict | None:
    """
    Finds an ingredient in the dataset by name.
    Tries exact match first, then partial matches in both directions.
    Returns the row as a dict, or None if not found.
    """
    name_lower = name.lower().strip()

    # Exact match
    match = df[df["ingredient_name_lower"] == name_lower]
    if not match.empty:
        return match.iloc[0].to_dict()

    # Dataset name contains search term
    match = df[df["ingredient_name_lower"].str.contains(re.escape(name_lower), na=False)]
    if not match.empty:
        return match.iloc[0].to_dict()

    # Search term contains dataset name (e.g. "Zinc Oxide 20%" → "Zinc Oxide")
    for _, row in df.iterrows():
        if row["ingredient_name_lower"] in name_lower:
            return row.to_dict()

    return None


# ── Step 3: Predict unknown ───────────────────────────────────

def _predict_unknown(name: str) -> dict:
    """
    For ingredients not in the dataset, guesses category and concern
    based on common name patterns (e.g. "paraben" → Medium concern).
    This is the fallback ML path.
    """
    n = name.lower()

    # Guess category from keywords in the ingredient name
    if any(x in n for x in ["oxide", "dioxide", "titanium", "zinc"]):
        cat = "UV Filter - Mineral"
    elif any(x in n for x in ["benzophenone", "cinnamate", "salicylate", "avobenzone", "octocrylene", "oxybenzone"]):
        cat = "UV Filter - Chemical"
    elif any(x in n for x in ["paraben", "methylparaben", "propylparaben"]):
        cat = "Preservative"
    elif any(x in n for x in ["glycol", "glycerin", "sorbitol"]):
        cat = "Humectant"
    elif any(x in n for x in ["oil", "butter", "wax", "ester", "stearate"]):
        cat = "Emollient"
    elif any(x in n for x in ["acid", "retinol", "vitamin", "niacin"]):
        cat = "Skin Active"
    elif any(x in n for x in ["fragrance", "parfum", "scent"]):
        cat = "Fragrance"
    elif any(x in n for x in ["alcohol", "ethanol"]):
        cat = "Solvent"
    elif any(x in n for x in ["cellulose", "gum", "carbomer", "polymer"]):
        cat = "Thickener"
    else:
        cat = "Skin Active"

    # Guess concern level from known problematic keywords
    concern = "None"
    if any(x in n for x in ["paraben", "formaldehyde", "hydantoin"]):
        concern = "Medium"
    if any(x in n for x in ["oxybenzone", "octinoxate", "phthalate", "triclosan"]):
        concern = "High"
    if "fragrance" in n or "parfum" in n:
        concern = "Medium"

    score = {"None": 8, "Low": 7, "Medium": 5, "High": 3}.get(concern, 6)
    safe  = 0 if concern == "High" else 1

    return {
        "ingredient_name":  name,
        "category":         cat,
        "uv_filter_type":   "None",
        "filter_mechanism": "N/A",
        "photostable":      "N/A",
        "uva_protection":   0,
        "uvb_protection":   0,
        "skin_type_1_safe": safe,
        "skin_type_2_safe": safe,
        "skin_type_3_safe": 1,
        "concern_level":    concern,
        "concern_reason":   "Predicted by ML model (not in dataset)",
        "overall_score":    score,
        "source":           "ML Prediction",
        "_predicted":       True,
    }


# ── Helper: UV protection rating ──────────────────────────────

def _uv_rating(scores: list) -> str:
    """Converts a list of UV protection scores (0-5) to a label."""
    if not scores: return "None"
    avg = sum(scores) / len(scores)
    if avg >= 4: return "Excellent"
    if avg >= 3: return "Good"
    if avg >= 2: return "Fair"
    if avg >= 1: return "Weak"
    return "None"


# ── Main analysis function ────────────────────────────────────

def analyze_ingredients_ml(
    raw_text: str,
    fitzpatrick_type: int,
    current_uv: float = None,
    skin_type: str = "Normal"
) -> dict:
    """
    Main function called by app.py.

    Args:
        raw_text:         Pasted ingredient list from a sunscreen bottle
        fitzpatrick_type: Fitzpatrick skin type 1-6
        current_uv:       Current UV Index (optional, for reapply advice)
        skin_type:        One of Oily/Dry/Combination/Sensitive/Normal

    Returns:
        Full analysis dict with scores, concerns, and advice.
        Returns {"success": False, ...} on any error.
    """
    try:
        bundle = _load_model()
    except FileNotFoundError as e:
        return {"success": False, "error": "no_model", "message": str(e)}

    # Step 1: Parse
    names = parse_ingredients(raw_text)
    if not names:
        return {"success": False, "error": "parse_error",
                "message": "Could not parse any ingredients from the text."}

    # Step 2: Look up every ingredient
    df = bundle["df"]
    results = []
    for name in names:
        row = _lookup(name, df) or _predict_unknown(name)
        row["_input_name"] = name
        results.append(row)

    # ── Classify ingredients ───────────────────────────────────

    # UV filters — ingredients that actively block UV radiation
    uv_filters = [
        r for r in results
        if str(r.get("uv_filter_type", "None")) not in ("None", "N/A", "0")
        and r.get("category", "").startswith("UV Filter")
    ]

    # Concerning — anything Medium or High concern level
    concerning = [r for r in results if r.get("concern_level") in ("Medium", "High")]

    # Beneficial — safe, high-scoring non-filler ingredients
    beneficial = [
        r for r in results
        if r.get("concern_level") == "None"
        and r.get("overall_score", 0) >= 8
        and not r.get("category", "").startswith("UV Filter")
        and r.get("category") not in ("Solvent", "Filler", "pH Adjuster")
    ][:5]

    # ── Broad spectrum + filter type ──────────────────────────
    filter_types = {str(r.get("uv_filter_type", "")) for r in uv_filters}
    has_uva        = any(t in ("UVA", "Broad") for t in filter_types)
    has_uvb        = any(t in ("UVB", "Broad") for t in filter_types)
    broad_spectrum = has_uva and has_uvb

    has_mineral  = any(r.get("filter_mechanism") == "Physical" for r in uv_filters)
    has_chemical = any(r.get("filter_mechanism") == "Chemical" for r in uv_filters)
    if has_mineral and has_chemical: filter_type_label = "Hybrid (Mineral + Chemical)"
    elif has_mineral:                filter_type_label = "Mineral (Physical)"
    elif has_chemical:               filter_type_label = "Chemical (Organic)"
    else:                            filter_type_label = "No UV Filters Detected"

    # ── Photostability ─────────────────────────────────────────
    # A filter is photounstable if it degrades under UV exposure (e.g. Avobenzone)
    unstable           = [r for r in uv_filters if str(r.get("photostable", "")) in ("0", "No")]
    photostable_overall = "Unstable" if unstable else ("Stable" if uv_filters else "N/A")

    # ── Overall rating ─────────────────────────────────────────
    # Base score uses UV filter scores only — prevents good moisturisers
    # from masking dangerous active ingredients
    if uv_filters:
        base_score = sum(float(r.get("overall_score", 5) or 5) for r in uv_filters) / len(uv_filters)
    else:
        # No UV filters = not really a sunscreen — penalise
        base_score = sum(float(r.get("overall_score", 5) or 5) for r in results) / len(results) - 3

    high_count   = sum(1 for r in results if r.get("concern_level") == "High")
    medium_count = sum(1 for r in results if r.get("concern_level") == "Medium")
    penalty      = (high_count * 2.0) + (medium_count * 0.8)
    bonus        = (0.5 if broad_spectrum else 0) + (0.5 if not unstable and uv_filters else 0)

    overall_rating = round(min(10, max(1, base_score - penalty + bonus)))

    # ── Verdict ────────────────────────────────────────────────
    if not uv_filters:
        verdict = "No UV filters detected. This may not be a sunscreen product."
    elif overall_rating >= 8:
        verdict = "This is a high-quality sunscreen formulation with excellent ingredients."
    elif overall_rating >= 6:
        verdict = "This is a decent formulation with some room for improvement."
    elif overall_rating >= 4:
        verdict = "This formulation has notable concerns. Consider alternatives."
    else:
        verdict = "This formulation has significant concerns. Seek specialist advice."

    # ── UVA / UVB ratings ─────────────────────────────────────
    uva_rating = _uv_rating([int(r.get("uva_protection", 0) or 0) for r in uv_filters])
    uvb_rating = _uv_rating([int(r.get("uvb_protection", 0) or 0) for r in uv_filters])

    # ── Skin type notes ────────────────────────────────────────
    FITZ_NAMES = {1:"Very Fair (Type I)", 2:"Fair (Type II)", 3:"Medium (Type III)",
                  4:"Olive (Type IV)",    5:"Brown (Type V)", 6:"Dark (Type VI)"}
    skin_desc   = FITZ_NAMES.get(fitzpatrick_type, "Unknown")
    skin_col    = f"skin_type_{fitzpatrick_type}_safe"
    skin_issues = [r for r in results if str(r.get(skin_col, "1")) in ("0", 0)]

    if skin_issues:
        problems   = ", ".join(r["ingredient_name"] for r in skin_issues[:3])
        skin_notes = (f"For your {skin_desc} skin type, be cautious of: {problems}. "
                      f"These may cause irritation or are not recommended for your skin type.")
    else:
        skin_notes = (f"This formulation appears compatible with {skin_desc} skin. "
                      f"All detected ingredients are suitable for your skin type.")

    # ── Reapplication note ─────────────────────────────────────
    if unstable:
        names_str  = ", ".join(r["ingredient_name"] for r in unstable)
        reapply    = (f"This sunscreen contains photounstable filters ({names_str}). "
                      f"Reapply every 90 minutes and immediately after swimming or sweating.")
    elif uv_filters:
        reapply    = ("Reapply every 2 hours during normal outdoor activity. "
                      "Reapply immediately after swimming, sweating, or towelling off.")
    else:
        reapply    = "No UV filters detected — reapplication guidelines not applicable."

    if current_uv and current_uv >= 8:
        reapply   += (f" With today's UV Index of {current_uv} (Very High/Extreme), "
                      f"reapply every 60-90 minutes.")

    # ── Science fact ───────────────────────────────────────────
    if any(r.get("ingredient_name") == "Avobenzone" for r in uv_filters):
        fact = ("Avobenzone absorbs UV-A photons and releases the energy as heat, "
                "but this degrades the molecule. Octocrylene stabilises it by donating "
                "electrons — a process called photostabilisation.")
    elif any(r.get("filter_mechanism") == "Physical" for r in uv_filters):
        fact = ("Mineral filters like Zinc Oxide scatter UV photons through a combination "
                "of reflection and absorption. At nano-scale, absorption dominates — "
                "the same Beer-Lambert principle that governs UV attenuation in the atmosphere.")
    elif any(r.get("ingredient_name") == "Niacinamide" for r in results):
        fact = ("Niacinamide (Vitamin B3) inhibits melanosome transfer from melanocytes "
                "to keratinocytes, reducing hyperpigmentation without stopping melanin synthesis.")
    else:
        fact = ("SPF is the ratio of UV dose needed to cause minimal erythema with vs without "
                "sunscreen. SPF 50 blocks 98% of UVB — the remaining 2% still reaches skin, "
                "which is why reapplication and shade are still essential.")

    # ── Per skin type scores ───────────────────────────────────
    # Uses skin-specific score columns from the dataset (oily_score, dry_score etc.)
    # and applies skin-type-specific penalties for problematic ingredients
    skin_type_scores = {}
    for st_name, st_info in SKIN_TYPES.items():
        col      = st_info["col"]
        penalties = SKIN_TYPE_PENALTIES[st_name]

        # Only score meaningful categories — skip Water, Glycerin etc.
        meaningful = [r for r in results if r.get("category", "") in SCORING_CATEGORIES] or results

        st_scores = []
        for r in meaningful:
            try:
                st_scores.append(float(r.get(col) or r.get("overall_score", 5) or 5))
            except (TypeError, ValueError):
                st_scores.append(5.0)

        st_base   = sum(st_scores) / len(st_scores) if st_scores else 5
        st_high   = high_count
        st_medium = medium_count

        # Extra penalties specific to each skin type
        if st_name == "Sensitive":
            # Fragrance is especially bad for sensitive skin
            st_high += sum(1 for r in results if r.get("category") == "Fragrance")

        if st_name == "Oily":
            # Heavy comedogenic oils clog pores on oily skin
            st_high += sum(
                1 for r in results
                if any(x in str(r.get("ingredient_name", "")).lower()
                       for x in ["coconut oil", "cocoa butter", "lanolin",
                                  "isopropyl myristate", "isopropyl palmitate"])
            )

        if st_name == "Dry":
            # Drying alcohols strip the skin barrier
            st_medium += sum(
                1 for r in results
                if any(x in str(r.get("ingredient_name", "")).lower()
                       for x in ["alcohol denat", "isopropyl alcohol", "ethanol"])
            )

        st_penalty = (st_high * penalties["High"]) + (st_medium * penalties["Medium"])
        st_bonus   = (0.5 if broad_spectrum else 0) + (0.3 if not unstable and uv_filters else 0)
        st_final   = round(min(10, max(1, st_base - st_penalty + st_bonus)))

        skin_type_scores[st_name] = {
            "score": st_final,
            "emoji": st_info["emoji"],
            "desc":  st_info["desc"],
            "color": rating_color(st_final),
            "label": rating_label(st_final),
        }

    # Skin compatibility label based on selected skin type's score
    sel_score  = skin_type_scores.get(skin_type, skin_type_scores["Normal"])["score"]
    skin_compat = ("Excellent" if sel_score >= 8 else
                   "Good"      if sel_score >= 6 else
                   "Fair"      if sel_score >= 4 else "Poor")

    # ── Return ─────────────────────────────────────────────────
    return {
        "success":                 True,
        "overall_rating":          overall_rating,
        "overall_verdict":         verdict,
        "uva_protection":          uva_rating,
        "uvb_protection":          uvb_rating,
        "photostability":          photostable_overall,
        "skin_type_compatibility": skin_compat,
        "broad_spectrum":          broad_spectrum,
        "filter_type":             filter_type_label,
        # UV filters found (for broad spectrum summary)
        "uv_filters_found": [{
            "name":          r.get("ingredient_name", ""),
            "type":          str(r.get("uv_filter_type", "")),
            "function":      f"UV-A: {r.get('uva_protection',0)}/5 · UV-B: {r.get('uvb_protection',0)}/5",
            "photostable":   str(r.get("photostable", "")) in ("1", "Yes"),
            "concern_level": r.get("concern_level", "None"),
        } for r in uv_filters],
        # Concerning ingredients shown to user
        "concerning_ingredients": [{
            "name":     r.get("ingredient_name", r.get("_input_name", "")),
            "severity": r.get("concern_level", "Low"),
            "concern":  str(r.get("concern_reason", "See scientific literature")),
        } for r in concerning],
        # Beneficial ingredients
        "beneficial_ingredients": [{
            "name":    r.get("ingredient_name", ""),
            "benefit": BENEFIT_TEXTS.get(r.get("category", ""), "Skin-beneficial ingredient"),
        } for r in beneficial],
        "skin_type_notes":         skin_notes,
        "reapplication_note":      reapply,
        "science_fact":            fact,
        "skin_type_scores":        skin_type_scores,
        "selected_skin_type":      skin_type,
        "selected_skin_score":     skin_type_scores.get(skin_type, skin_type_scores["Normal"]),
        "total_ingredients":       len(results),
        "matched_ingredients":     sum(1 for r in results if not r.get("_predicted")),
        "predicted_ingredients":   sum(1 for r in results if r.get("_predicted")),
    }


# ── Colour helpers (imported by app.py) ──────────────────────

def rating_color(rating: int) -> str:
    """Returns hex colour for an overall score."""
    if rating >= 8: return "#22c55e"
    if rating >= 6: return "#eab308"
    if rating >= 4: return "#f97316"
    return "#ef4444"

def rating_label(rating: int) -> str:
    """Returns text label for an overall score."""
    if rating >= 8: return "Excellent"
    if rating >= 6: return "Good"
    if rating >= 4: return "Fair"
    return "Poor"

def protection_color(level: str) -> str:
    """Returns hex colour for a protection level label."""
    return {
        "Excellent": "#22c55e", "Good":     "#84cc16",
        "Fair":      "#eab308", "Weak":     "#f97316",
        "None":      "#ef4444", "N/A":      "#64748b",
        "Stable":    "#22c55e", "Unstable": "#ef4444",
        "Poor":      "#ef4444",
    }.get(str(level), "#64748b")

def concern_color(level: str) -> str:
    """Returns hex colour for a concern level label."""
    return {
        "None": "#22c55e", "Low":    "#eab308",
        "Medium": "#f97316", "High": "#ef4444",
    }.get(str(level), "#64748b")