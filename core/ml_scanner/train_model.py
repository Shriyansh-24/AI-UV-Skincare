# ============================================================
# Solara — core/ml_scanner/train_model.py
# Trains the Random Forest ML model from ingredients.csv
#
# RUN ONCE from project root:
#   python core/ml_scanner/train_model.py
#
# OUTPUT:
#   core/ml_scanner/model.pkl  ← loaded by predict.py at runtime
#
# WHAT IT TRAINS:
#   Model 1 — Concern Level Classifier (High/Medium/Low/None)
#   Model 2 — Overall Score Regressor  (1-10)
# ============================================================

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, "ingredients.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

print("=" * 55)
print("  Solara ML Pipeline — Training")
print("=" * 55)

# ── Step 1: Load ──────────────────────────────────────────────
print("\n📂 Loading dataset...")
df = pd.read_csv(DATA_PATH)
print(f"   ✅ {len(df)} ingredients loaded")

# ── Step 2: Clean ─────────────────────────────────────────────
print("\n🧹 Cleaning data...")

# Lowercase names for consistent matching at runtime
df["ingredient_name_lower"] = df["ingredient_name"].str.lower().str.strip()

# Convert Yes/No/N/A columns to 1/0
for col in ["photostable", "eu_approved", "fda_approved",
            "skin_type_1_safe", "skin_type_2_safe", "skin_type_3_safe"]:
    df[col] = df[col].map({"Yes": 1, "No": 0, "N/A": 0}).fillna(0).astype(int)

# Ensure numeric columns are clean
for col in ["uva_protection", "uvb_protection", "overall_score"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0 if col != "overall_score" else 5)

# Encode categorical columns as integers for the ML model
label_encoders = {}
for col in ["category", "uv_filter_type", "filter_mechanism", "concern_level", "eu_approved", "fda_approved"]:
    le = LabelEncoder()
    df[col + "_enc"] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le
    print(f"   Encoded '{col}': {list(le.classes_)}")

print("   ✅ Done")

# ── Step 3: Features & targets ────────────────────────────────
print("\n🎯 Preparing features...")

# These are the columns the model uses to make predictions
FEATURES = [
    "category_enc", "uv_filter_type_enc", "filter_mechanism_enc",
    "photostable", "uva_protection", "uvb_protection",
    "eu_approved", "fda_approved",
    "skin_type_1_safe", "skin_type_2_safe", "skin_type_3_safe",
]

X         = df[FEATURES]
y_concern = df["concern_level_enc"]   # target: concern level class
y_score   = df["overall_score"]       # target: 1-10 safety score

print(f"   Features: {FEATURES}")
print(f"   Samples:  {len(X)}")

# ── Step 4: Train / test split ────────────────────────────────
print("\n✂️  Splitting (80% train / 20% test)...")
X_train, X_test, yc_train, yc_test, ys_train, ys_test = train_test_split(
    X, y_concern, y_score, test_size=0.2, random_state=42
)
print(f"   Train: {len(X_train)}  |  Test: {len(X_test)}")

# ── Step 5: Train ─────────────────────────────────────────────
print("\n🌲 Training Random Forest models...")

# Classifier: predicts concern level (High / Medium / Low / None)
# class_weight="balanced" compensates for the imbalanced dataset
# (210 "None" vs only 19 "High" examples)
clf_concern = RandomForestClassifier(
    n_estimators=200, max_depth=10,
    min_samples_split=2, random_state=42,
    class_weight="balanced"
)
clf_concern.fit(X_train, yc_train)

# Regressor: predicts overall safety score (1-10)
clf_score = RandomForestRegressor(
    n_estimators=200, max_depth=10, random_state=42
)
clf_score.fit(X_train, ys_train)

print("   ✅ Both models trained")

# ── Step 6: Evaluate ──────────────────────────────────────────
print("\n📊 Evaluation:")
print("-" * 40)

yc_pred = clf_concern.predict(X_test)
acc     = accuracy_score(yc_test, yc_pred)
print(f"\n   Concern Classifier Accuracy: {acc*100:.1f}%")
print(classification_report(
    yc_test, yc_pred,
    target_names=[str(c) for c in label_encoders["concern_level"].classes_],
    zero_division=0
))

ys_pred = clf_score.predict(X_test)
mae     = np.mean(np.abs(ys_pred - ys_test))
print(f"   Score Regressor MAE: {mae:.2f} / 10")

print("\n   🔍 Top Feature Importances:")
for feat, imp in sorted(zip(FEATURES, clf_concern.feature_importances_), key=lambda x: -x[1])[:6]:
    print(f"   {feat:<35} {'█' * int(imp * 40)}  {imp:.3f}")

# ── Step 7: Save ──────────────────────────────────────────────
print("\n💾 Saving model.pkl...")

with open(MODEL_PATH, "wb") as f:
    pickle.dump({
        "clf_concern":    clf_concern,
        "clf_score":      clf_score,
        "label_encoders": label_encoders,
        "features":       FEATURES,
        "df":             df,      # full dataset for ingredient lookup at runtime
        "version":        "1.0",
    }, f)

print(f"   ✅ Saved ({os.path.getsize(MODEL_PATH) // 1024} KB) → {MODEL_PATH}")
print("\n" + "=" * 55)
print("  ✅ Done! Run: streamlit run app.py")
print("=" * 55)