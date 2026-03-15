# ============================================================
# Solara — core/ml_scanner/predict.py
# Runtime ML predictions for the ingredient scanner
# Used by app.py — do NOT run this directly
# ============================================================

import os
import re
import pickle
import pandas as pd
import numpy as np

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

# ── Skin type configuration ──────────────────────────────────
SKIN_TYPES = {
    "Oily":        {"col": "oily_score",        "emoji": "💧", "desc": "Oily Skin"},
    "Dry":         {"col": "dry_score",          "emoji": "🌵", "desc": "Dry Skin"},
    "Combination": {"col": "combination_score",  "emoji": "⚖️", "desc": "Combination Skin"},
    "Sensitive":   {"col": "sensitive_score",    "emoji": "🌸", "desc": "Sensitive Skin"},
    "Normal":      {"col": "normal_score",       "emoji": "✨", "desc": "Normal Skin"},
}

# ── Load model once at import time ───────────────────────────
_bundle = None

def _load_model():
    global _bundle
    if _bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                "model.pkl not found. Run train_model.py first:\n"
                "  python core/ml_scanner/train_model.py"
            )
        with open(MODEL_PATH, "rb") as f:
            _bundle = pickle.load(f)
    return _bundle


# ══════════════════════════════════════════════════════════════
#  INGREDIENT TEXT PARSER
# ══════════════════════════════════════════════════════════════
def parse_ingredients(raw_text: str) -> list:
    """
    Parses a raw ingredient label into a clean list of names.

    Handles formats like:
      - "Avobenzone 3%, Homosalate 10%, ..."
      - "Active Ingredients: ...\nInactive Ingredients: ..."
      - "Water, Glycerin, Niacinamide (10%), ..."
    """
    # Remove section headers
    text = re.sub(
        r"(active\s+ingredients?|inactive\s+ingredients?|ingredients?)\s*:",
        ",", raw_text, flags=re.IGNORECASE
    )
    # Split on commas and newlines
    parts = re.split(r"[,\n;]+", text)

    cleaned = []
    for part in parts:
        # Remove percentages, numbers, brackets
        name = re.sub(r"\d+\.?\d*\s*%", "", part)
        name = re.sub(r"\(.*?\)", "", name)
        name = name.strip().strip(".-/").strip()
        if len(name) > 2:
            cleaned.append(name)

    return cleaned


# ══════════════════════════════════════════════════════════════
#  SINGLE INGREDIENT LOOKUP
# ══════════════════════════════════════════════════════════════
def lookup_ingredient(name: str, bundle: dict) -> dict | None:
    """
    Looks up an ingredient in the dataset by exact or fuzzy name match.
    Returns the full row as a dict, or None if not found.
    """
    df = bundle["df"]
    name_lower = name.lower().strip()

    # Exact match on ingredient_name_lower
    match = df[df["ingredient_name_lower"] == name_lower]
    if not match.empty:
        return match.iloc[0].to_dict()

    # Partial match — ingredient name contains the search term
    match = df[df["ingredient_name_lower"].str.contains(
        re.escape(name_lower), na=False)]
    if not match.empty:
        return match.iloc[0].to_dict()

    # Reverse partial — search term contains the ingredient name
    for _, row in df.iterrows():
        if row["ingredient_name_lower"] in name_lower:
            return row.to_dict()

    return None


# ══════════════════════════════════════════════════════════════
#  ML PREDICTION FOR UNKNOWN INGREDIENTS
# ══════════════════════════════════════════════════════════════
def predict_unknown(name: str, bundle: dict) -> dict:
    """
    For ingredients not in the dataset, uses the ML model to predict
    concern level and score based on name patterns.
    """
    # Simple heuristics based on ingredient name patterns
    name_lower = name.lower()

    # Guess category from name
    if any(x in name_lower for x in ["oxide", "dioxide", "titanium", "zinc"]):
        cat = "UV Filter - Mineral"
    elif any(x in name_lower for x in ["benzophenone", "cinnamate", "salicylate",
                                         "avobenzone", "octocrylene", "oxybenzone"]):
        cat = "UV Filter - Chemical"
    elif any(x in name_lower for x in ["paraben", "methylparaben", "propylparaben"]):
        cat = "Preservative"
    elif any(x in name_lower for x in ["glycol", "glycerin", "sorbitol"]):
        cat = "Humectant"
    elif any(x in name_lower for x in ["oil", "butter", "wax", "ester", "stearate"]):
        cat = "Emollient"
    elif any(x in name_lower for x in ["acid", "retinol", "vitamin", "niacin"]):
        cat = "Skin Active"
    elif any(x in name_lower for x in ["fragrance", "parfum", "scent"]):
        cat = "Fragrance"
    elif any(x in name_lower for x in ["alcohol", "ethanol"]):
        cat = "Solvent"
    elif any(x in name_lower for x in ["cellulose", "gum", "carbomer", "polymer"]):
        cat = "Thickener"
    else:
        cat = "Skin Active"

    # Concern heuristics
    concern = "None"
    if any(x in name_lower for x in ["paraben", "formaldehyde", "hydantoin"]):
        concern = "Medium"
    if any(x in name_lower for x in ["oxybenzone", "octinoxate", "phthalate", "triclosan"]):
        concern = "High"
    if "fragrance" in name_lower or "parfum" in name_lower:
        concern = "Medium"

    # Score heuristic
    score_map = {"None": 8, "Low": 7, "Medium": 5, "High": 3}
    score = score_map.get(concern, 6)

    return {
        "ingredient_name": name,
        "category": cat,
        "uv_filter_type": "None",
        "filter_mechanism": "N/A",
        "photostable": "N/A",
        "uva_protection": 0,
        "uvb_protection": 0,
        "skin_type_1_safe": 1 if concern != "High" else 0,
        "skin_type_2_safe": 1 if concern != "High" else 0,
        "skin_type_3_safe": 1,
        "skin_type_4_safe": 1,
        "skin_type_5_safe": 1,
        "skin_type_6_safe": 1,
        "concern_level": concern,
        "concern_reason": "Predicted by ML model (not in dataset)",
        "eu_approved": "Unknown",
        "fda_approved": "Unknown",
        "overall_score": score,
        "source": "ML Prediction",
        "_predicted": True,
    }


# ══════════════════════════════════════════════════════════════
#  MAIN ANALYSIS FUNCTION
# ══════════════════════════════════════════════════════════════
def analyze_ingredients_ml(raw_text: str, fitzpatrick_type: int,
                            current_uv: float = None,
                            skin_type: str = "Normal") -> dict:
    """
    Main function called by app.py.
    Takes raw ingredient label text, returns full analysis dict.

    Args:
        raw_text:        Pasted ingredient list from sunscreen bottle
        fitzpatrick_type: 1-6 Fitzpatrick skin type
        current_uv:      Current UV Index (optional, for context)

    Returns:
        dict with full analysis results
    """
    try:
        bundle = _load_model()
    except FileNotFoundError as e:
        return {"success": False, "error": "no_model", "message": str(e)}

    # ── Step 1: Parse ingredient names ───────────────────────
    ingredients = parse_ingredients(raw_text)
    if not ingredients:
        return {
            "success": False,
            "error": "parse_error",
            "message": "Could not parse any ingredients from the text."
        }

    # ── Step 2: Look up each ingredient ──────────────────────
    skin_col = f"skin_type_{fitzpatrick_type}_safe"
    results  = []

    for name in ingredients:
        row = lookup_ingredient(name, bundle)
        if row is None:
            row = predict_unknown(name, bundle)
        row["_input_name"] = name
        results.append(row)

    if not results:
        return {
            "success": False,
            "error": "no_matches",
            "message": "No ingredients could be matched."
        }

    # ── Step 3: Identify UV filters ──────────────────────────
    uv_filters = [
        r for r in results
        if str(r.get("uv_filter_type", "None")) not in ("None", "N/A", "0")
        and r.get("category", "").startswith("UV Filter")
    ]

    # ── Step 4: Identify concerning ingredients ───────────────
    concerning = [
        r for r in results
        if r.get("concern_level") in ("Medium", "High")
    ]

    # ── Step 5: Identify beneficial ingredients ───────────────
    beneficial = [
        r for r in results
        if r.get("concern_level") == "None"
        and r.get("overall_score", 0) >= 8
        and not r.get("category", "").startswith("UV Filter")
        and r.get("category") not in ("Solvent", "Filler", "pH Adjuster")
    ][:6]

    # ── Step 6: Broad spectrum check ─────────────────────────
    filter_types = {str(r.get("uv_filter_type", "")) for r in uv_filters}
    has_uva  = any(t in ("UVA", "Broad") for t in filter_types)
    has_uvb  = any(t in ("UVB", "Broad") for t in filter_types)
    broad_spectrum = has_uva and has_uvb

    # Determine filter type label
    has_mineral  = any(r.get("filter_mechanism") == "Physical" for r in uv_filters)
    has_chemical = any(r.get("filter_mechanism") == "Chemical" for r in uv_filters)
    if has_mineral and has_chemical:
        filter_type_label = "Hybrid (Mineral + Chemical)"
    elif has_mineral:
        filter_type_label = "Mineral (Physical)"
    elif has_chemical:
        filter_type_label = "Chemical (Organic)"
    else:
        filter_type_label = "No UV Filters Detected"

    # ── Step 7: Photostability check ─────────────────────────
    unstable = [r for r in uv_filters
                if str(r.get("photostable", "")) in ("0", "No")]
    photostable_overall = "Unstable" if unstable else ("Stable" if uv_filters else "N/A")

    # ── Step 8: Skin type compatibility ──────────────────────
    skin_issues = [
        r for r in results
        if str(r.get(skin_col, "1")) in ("0", 0)
    ]
    if not skin_issues:
        skin_compat = "Excellent"
    elif len(skin_issues) <= 1:
        skin_compat = "Good"
    elif len(skin_issues) <= 3:
        skin_compat = "Fair"
    else:
        skin_compat = "Poor"

    # ── Step 9: UVA / UVB protection rating ──────────────────
    def uv_rating(scores):
        if not scores: return "None"
        avg = sum(scores) / len(scores)
        if avg >= 4: return "Excellent"
        if avg >= 3: return "Good"
        if avg >= 2: return "Fair"
        if avg >= 1: return "Weak"
        return "None"

    uva_scores = [int(r.get("uva_protection", 0) or 0) for r in uv_filters]
    uvb_scores = [int(r.get("uvb_protection", 0) or 0) for r in uv_filters]

    # ── Step 10: Overall rating ───────────────────────────────
    # Only score UV filters and HIGH concern ingredients for the base
    # This prevents good inactive ingredients from masking bad actives

    if uv_filters:
        # Score based on UV filters only — these are what matter most
        filter_scores = [float(r.get("overall_score", 5) or 5) for r in uv_filters]
        base_score = sum(filter_scores) / len(filter_scores)
    else:
        # No UV filters — score from all ingredients but penalise heavily
        all_scores = [float(r.get("overall_score", 5) or 5) for r in results]
        base_score = sum(all_scores) / len(all_scores) - 3

    # Strong penalties — each High concern ingredient is a serious issue
    high_concern_count   = sum(1 for r in results if r.get("concern_level") == "High")
    medium_concern_count = sum(1 for r in results if r.get("concern_level") == "Medium")
    penalty = (high_concern_count * 2.0) + (medium_concern_count * 0.8)

    # Bonuses
    bonus = 0
    if broad_spectrum:              bonus += 0.5
    if not unstable and uv_filters: bonus += 0.5

    overall_rating = round(min(10, max(1, base_score - penalty + bonus)))

    # ── Step 11: Build verdict ────────────────────────────────
    if overall_rating >= 8:
        verdict = "This is a high-quality sunscreen formulation with excellent ingredients."
    elif overall_rating >= 6:
        verdict = "This is a decent formulation with some room for improvement."
    elif overall_rating >= 4:
        verdict = "This formulation has notable concerns. Consider alternatives."
    else:
        verdict = "This formulation has significant concerns. Seek specialist advice."

    if not uv_filters:
        verdict = "No UV filters detected. This may not be a sunscreen product."

    # ── Step 12: Skin type notes ──────────────────────────────
    skin_type_descriptions = {
        1: "Very Fair (Type I)", 2: "Fair (Type II)",
        3: "Medium (Type III)",  4: "Olive (Type IV)",
        5: "Brown (Type V)",     6: "Dark (Type VI)"
    }
    skin_desc = skin_type_descriptions.get(fitzpatrick_type, "Unknown")

    skin_col   = f"skin_type_{fitzpatrick_type}_safe"
    skin_issues = [r for r in results if str(r.get(skin_col, "1")) in ("0", 0)]

    if skin_issues:
        problem_names = ", ".join(r["ingredient_name"] for r in skin_issues[:3])
        skin_notes = (f"For your {skin_desc} skin type, be cautious of: "
                     f"{problem_names}. These ingredients may cause irritation "
                     f"or are not recommended for your skin type.")
    else:
        skin_notes = (f"This formulation appears compatible with {skin_desc} skin. "
                     f"All detected ingredients are suitable for your skin type.")

    # ── Step 13: Reapplication note ───────────────────────────
    if unstable:
        unstable_names = ", ".join(r["ingredient_name"] for r in unstable)
        reapply_note = (f"This sunscreen contains photounstable filters "
                       f"({unstable_names}). Reapply every 90 minutes when "
                       f"outdoors, and immediately after swimming or sweating.")
    elif uv_filters:
        reapply_note = ("Reapply every 2 hours during normal outdoor activity. "
                       "Reapply immediately after swimming, sweating, or towelling off.")
    else:
        reapply_note = "No UV filters detected — reapplication guidelines not applicable."

    if current_uv and current_uv >= 8:
        reapply_note += (f" With today's UV Index of {current_uv} (Very High/Extreme), "
                        f"reapply every 60-90 minutes.")

    # ── Step 14: Science fact ─────────────────────────────────
    science_facts = []
    if any(r.get("ingredient_name") == "Avobenzone" for r in uv_filters):
        science_facts.append(
            "Avobenzone absorbs UV-A photons and releases the energy as heat, "
            "but this process degrades the molecule. Octocrylene donates electrons "
            "to restore avobenzone — a photostabilisation mechanism.")
    if any(r.get("filter_mechanism") == "Physical" for r in uv_filters):
        science_facts.append(
            "Mineral filters like Zinc Oxide work by scattering UV photons "
            "through a combination of reflection and absorption. At nano-scale, "
            "absorption dominates over reflection — the same Beer-Lambert principle "
            "that governs UV attenuation in the atmosphere.")
    if any(r.get("ingredient_name") == "Niacinamide" for r in results):
        science_facts.append(
            "Niacinamide (Vitamin B3) inhibits the transfer of melanosomes from "
            "melanocytes to keratinocytes, reducing hyperpigmentation without "
            "inhibiting melanin synthesis itself.")
    if not science_facts:
        science_facts.append(
            "Sunscreen SPF is measured by the ratio of UV dose needed to cause "
            "minimal erythema with vs without sunscreen. SPF 50 blocks 98% of "
            "UVB; the remaining 2% still reaches skin — showing why reapplication "
            "and other protection methods remain essential.")

    # ── Step 15: Format UV filters for display ───────────────
    uv_filters_display = []
    for r in uv_filters:
        uv_filters_display.append({
            "name":          r.get("ingredient_name", ""),
            "type":          str(r.get("uv_filter_type", "")),
            "function":      "UV-A: " + str(r.get("uva_protection",0)) + "/5 · UV-B: " + str(r.get("uvb_protection",0)) + "/5",
            "photostable":   str(r.get("photostable", "")) in ("1", "Yes"),
            "concern_level": r.get("concern_level", "None"),
        })

    # Format concerning ingredients
    concerning_display = []
    for r in concerning:
        concerning_display.append({
            "name":     r.get("ingredient_name", r.get("_input_name", "")),
            "severity": r.get("concern_level", "Low"),
            "concern":  str(r.get("concern_reason", "See scientific literature")),
        })

    # Format beneficial ingredients
    beneficial_display = []
    for r in beneficial[:5]:
        benefit_text = {
            "Humectant":      "Draws moisture into the skin",
            "Emollient":      "Softens and smooths skin texture",
            "Antioxidant":    "Neutralises free radicals from UV exposure",
            "Soothing Agent": "Calms inflammation and reduces redness",
            "Skin Active":    "Active ingredient with targeted skin benefit",
        }.get(r.get("category", ""), "Skin-beneficial ingredient")
        beneficial_display.append({
            "name":    r.get("ingredient_name", ""),
            "benefit": benefit_text,
        })

    # ── Step 16: Per skin type score ─────────────────────────
    # Rules per skin type:
    # - Start from the skin-specific column scores for matched ingredients
    # - Only average ingredients that actually have a score (UV filters + actives)
    # - Apply skin-type-specific concern penalties
    # - Inactive base ingredients (water, glycerin etc.) are weighted low

    SKIN_TYPE_PENALTIES = {
        # Extra penalty per High concern ingredient per skin type
        "Oily":        {"High": 2.0, "Medium": 0.8},
        "Dry":         {"High": 2.0, "Medium": 0.8},
        "Combination": {"High": 2.0, "Medium": 0.8},
        "Sensitive":   {"High": 2.5, "Medium": 1.2},  # sensitive = harsher penalties
        "Normal":      {"High": 1.8, "Medium": 0.6},
    }

    # Categories that actually matter for scoring — skip filler ingredients
    SCORING_CATEGORIES = {
        "UV Filter - Chemical", "UV Filter - Mineral", "Photostabiliser",
        "Preservative", "Fragrance", "Skin Active", "Solvent"
    }

    skin_type_scores = {}
    for st_name, st_info in SKIN_TYPES.items():
        col = st_info["col"]
        penalties = SKIN_TYPE_PENALTIES[st_name]

        # Collect scores only from meaningful categories
        meaningful = [r for r in results if r.get("category", "") in SCORING_CATEGORIES]
        if not meaningful:
            meaningful = results  # fallback

        st_scores = []
        for r in meaningful:
            val = r.get(col)
            try:
                st_scores.append(float(val))
            except (TypeError, ValueError):
                st_scores.append(float(r.get("overall_score", 5) or 5))

        st_base = sum(st_scores) / len(st_scores) if st_scores else 5

        # Count concern levels for THIS skin type
        st_high   = sum(1 for r in results if r.get("concern_level") == "High")
        st_medium = sum(1 for r in results if r.get("concern_level") == "Medium")

        # Extra skin-type specific penalties
        # Sensitive skin: fragrance is extra bad
        if st_name == "Sensitive":
            fragrance_count = sum(1 for r in results if r.get("category") == "Fragrance")
            st_high += fragrance_count  # count fragrance as extra High for sensitive

        # Oily skin: heavy occlusive oils are bad
        if st_name == "Oily":
            comedogenic = sum(1 for r in results
                             if any(x in str(r.get("ingredient_name","")).lower()
                                   for x in ["coconut oil", "cocoa butter", "lanolin",
                                              "isopropyl myristate", "isopropyl palmitate"]))
            st_high += comedogenic

        # Dry skin: alcohol is bad
        if st_name == "Dry":
            drying = sum(1 for r in results
                        if any(x in str(r.get("ingredient_name","")).lower()
                              for x in ["alcohol denat", "isopropyl alcohol", "ethanol"]))
            st_medium += drying

        st_penalty = (st_high * penalties["High"]) + (st_medium * penalties["Medium"])
        st_bonus = 0
        if broad_spectrum:              st_bonus += 0.5
        if not unstable and uv_filters: st_bonus += 0.3

        st_final = round(min(10, max(1, st_base - st_penalty + st_bonus)))
        skin_type_scores[st_name] = {
            "score": st_final,
            "emoji": st_info["emoji"],
            "desc":  st_info["desc"],
            "color": rating_color(st_final),
            "label": rating_label(st_final),
        }

    # Skin compat based on skin type scores
    sel_score = skin_type_scores.get(skin_type, skin_type_scores["Normal"])["score"]
    if sel_score >= 8:   skin_compat = "Excellent"
    elif sel_score >= 6: skin_compat = "Good"
    elif sel_score >= 4: skin_compat = "Fair"
    else:                skin_compat = "Poor"

    selected_skin_score = skin_type_scores.get(skin_type, skin_type_scores["Normal"])

    # ── Return full analysis ──────────────────────────────────
    return {
        "success":                 True,
        "overall_rating":          overall_rating,
        "overall_verdict":         verdict,
        "uva_protection":          uv_rating(uva_scores),
        "uvb_protection":          uv_rating(uvb_scores),
        "photostability":          photostable_overall,
        "skin_type_compatibility": skin_compat,
        "broad_spectrum":          broad_spectrum,
        "filter_type":             filter_type_label,
        "uv_filters_found":        uv_filters_display,
        "concerning_ingredients":  concerning_display,
        "beneficial_ingredients":  beneficial_display,
        "skin_type_notes":         skin_notes,
        "reapplication_note":      reapply_note,
        "science_fact":            science_facts[0],
        "skin_type_scores":        skin_type_scores,
        "selected_skin_type":      skin_type,
        "selected_skin_score":     selected_skin_score,
        "total_ingredients":       len(results),
        "matched_ingredients":     sum(1 for r in results
                                       if not r.get("_predicted")),
        "predicted_ingredients":   sum(1 for r in results
                                       if r.get("_predicted")),
        "_source":                 "ML Model v1.0",
    }


# ── Colour helper functions (used by app.py) ──────────────────
def rating_color(rating: int) -> str:
    if rating >= 8: return "#22c55e"
    if rating >= 6: return "#eab308"
    if rating >= 4: return "#f97316"
    return "#ef4444"

def rating_label(rating: int) -> str:
    if rating >= 8: return "Excellent"
    if rating >= 6: return "Good"
    if rating >= 4: return "Fair"
    return "Poor"

def protection_color(level: str) -> str:
    mapping = {
        "Excellent": "#22c55e",
        "Good":      "#84cc16",
        "Fair":      "#eab308",
        "Weak":      "#f97316",
        "None":      "#ef4444",
        "N/A":       "#64748b",
        "Stable":    "#22c55e",
        "Unstable":  "#ef4444",
        "Poor":      "#ef4444",
    }
    return mapping.get(str(level), "#64748b")

def concern_color(level: str) -> str:
    mapping = {
        "None":   "#22c55e",
        "Low":    "#eab308",
        "Medium": "#f97316",
        "High":   "#ef4444",
    }
    return mapping.get(str(level), "#64748b")