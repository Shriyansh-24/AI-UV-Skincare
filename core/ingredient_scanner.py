# ============================================================
# UV Skincare Advisor — core/ingredient_scanner.py
# Responsible for: AI-powered sunscreen ingredient analysis
# AI Model: Groq (Llama 3.3 70B) — free, no credit card needed
# Team role: DATA REFINER owns the ingredient knowledge here
# ============================================================

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def get_groq_key() -> str | None:
    return os.getenv("GROQ_API_KEY")


def analyze_ingredients(ingredients_text, skin_type_id, uv_index=None):
    api_key = get_groq_key()

    if not api_key or api_key == "your_groq_key_here":
        return {
            "success": False,
            "error":   "no_api_key",
            "message": "Groq API key not found. Please add GROQ_API_KEY to your .env file."
        }

    skin_descriptions = {
        1: "Fitzpatrick Type I — Very fair, always burns, never tans",
        2: "Fitzpatrick Type II — Fair, usually burns, tans minimally",
        3: "Fitzpatrick Type III — Medium, sometimes burns, gradually tans",
        4: "Fitzpatrick Type IV — Olive, rarely burns, tans easily",
        5: "Fitzpatrick Type V — Brown, very rarely burns",
        6: "Fitzpatrick Type VI — Dark brown/black, never burns",
    }
    skin_desc  = skin_descriptions.get(skin_type_id, "Unknown skin type")
    uv_context = f"The current UV Index is {uv_index}." if uv_index else ""

    prompt = f"""
You are an expert cosmetic chemist and dermatologist specialising in UV protection science.

Analyse the following sunscreen ingredient list for a user with {skin_desc}. {uv_context}

INGREDIENT LIST:
{ingredients_text}

Respond ONLY with a valid JSON object — no extra text, no markdown, no backticks.
Use exactly this structure:

{{
  "overall_rating": <integer 1-10>,
  "overall_verdict": "<one sentence summary>",
  "broad_spectrum": <true or false>,
  "uva_protection": "<Poor / Moderate / Good / Excellent>",
  "uvb_protection": "<Poor / Moderate / Good / Excellent>",
  "filter_type": "<Chemical / Physical / Hybrid>",
  "photostability": "<Poor / Moderate / Good / Excellent>",
  "skin_type_compatibility": "<Poor / Moderate / Good / Excellent>",
  "uv_filters_found": [
    {{
      "name": "<ingredient name>",
      "type": "<UV-A filter / UV-B filter / Broad spectrum>",
      "function": "<one sentence explanation of how it works>",
      "photostable": <true or false>,
      "concern_level": "<None / Low / Moderate / High>"
    }}
  ],
  "beneficial_ingredients": [
    {{
      "name": "<ingredient name>",
      "benefit": "<why it is beneficial for this skin type>"
    }}
  ],
  "concerning_ingredients": [
    {{
      "name": "<ingredient name>",
      "concern": "<why it may be problematic>",
      "severity": "<Low / Moderate / High>"
    }}
  ],
  "skin_type_notes": "<2-3 sentences of personalised advice for this Fitzpatrick type>",
  "reapplication_note": "<advice on how this formula affects reapplication frequency>",
  "science_fact": "<one interesting chemistry or physics fact about a key ingredient>"
}}

Be accurate, science-based, and specific. Only include UV filters in uv_filters_found.
"""

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       GROQ_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens":  2048,
            },
            timeout=30
        )

        if response.status_code == 401:
            return {"success": False, "error": "bad_key",
                    "message": "Invalid Groq API key. Check your .env file."}
        if response.status_code == 429:
            return {"success": False, "error": "rate_limited",
                    "message": "Groq rate limit hit. Wait 30 seconds and try again."}

        response.raise_for_status()

        data     = response.json()
        raw_text = data["choices"][0]["message"]["content"].strip()

        # Clean any accidental markdown fences
        cleaned = raw_text
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()

        analysis = json.loads(cleaned)
        analysis["success"] = True
        return analysis

    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "no_internet",
                "message": "No internet connection."}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "timeout",
                "message": "Groq API timed out. Please try again."}
    except json.JSONDecodeError:
        return {"success": False, "error": "parse_error",
                "message": "Could not parse AI response. Try again."}
    except Exception as e:
        return {"success": False, "error": "unknown", "message": str(e)}


def rating_color(rating):
    if rating >= 8:   return "#4CAF50"
    elif rating >= 6: return "#FFC107"
    elif rating >= 4: return "#FF9800"
    else:             return "#F44336"


def rating_label(rating):
    if rating >= 8:   return "Excellent"
    elif rating >= 6: return "Good"
    elif rating >= 4: return "Fair"
    else:             return "Poor"


def protection_color(level):
    return {"Excellent": "#4CAF50", "Good": "#8BC34A",
            "Moderate": "#FFC107", "Poor": "#F44336"}.get(level, "#9E9E9E")


def concern_color(level):
    return {"None": "#4CAF50", "Low": "#8BC34A",
            "Moderate": "#FF9800", "High": "#F44336"}.get(level, "#9E9E9E")