# ============================================================
# Solara — core/ml_scanner/train_model.py
# Trains the ingredient analysis ML model from ingredients.csv
#
# HOW TO RUN (once, from project root):
#   python core/ml_scanner/train_model.py
#
# OUTPUT:
#   core/ml_scanner/model.pkl  ← saved model used by the app
# ============================================================

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# ── Paths ─────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "ingredients.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

print("=" * 55)
print("  Solara ML Pipeline — Training")
print("=" * 55)

# ══════════════════════════════════════════════════════════════
#  STEP 1 — LOAD DATA
# ══════════════════════════════════════════════════════════════
print("\n📂 Loading dataset...")
df = pd.read_csv(DATA_PATH)
print(f"   ✅ {len(df)} ingredients loaded")
print(f"   📊 Columns: {list(df.columns)}")

# ══════════════════════════════════════════════════════════════
#  STEP 2 — CLEAN & PREPARE
# ══════════════════════════════════════════════════════════════
print("\n🧹 Cleaning data...")

# Lowercase ingredient names for consistent matching
df["ingredient_name_lower"] = df["ingredient_name"].str.lower().str.strip()

# Convert Yes/No columns to 1/0
binary_cols = [
    "photostable", "eu_approved", "fda_approved",
    "skin_type_1_safe", "skin_type_2_safe", "skin_type_3_safe",
]
for col in binary_cols:
    df[col] = df[col].map({"Yes": 1, "No": 0, "N/A": 0}).fillna(0).astype(int)

# Fill missing numeric values
df["uva_protection"] = pd.to_numeric(df["uva_protection"], errors="coerce").fillna(0)
df["uvb_protection"] = pd.to_numeric(df["uvb_protection"], errors="coerce").fillna(0)
df["overall_score"]  = pd.to_numeric(df["overall_score"],  errors="coerce").fillna(5)

# ── Encode categorical columns ────────────────────────────────
label_encoders = {}

for col in ["category", "uv_filter_type", "filter_mechanism",
            "concern_level", "eu_approved", "fda_approved"]:
    le = LabelEncoder()
    df[col + "_enc"] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le
    print(f"   Encoded '{col}': {list(le.classes_)}")

print("   ✅ Data cleaned and encoded")

# ══════════════════════════════════════════════════════════════
#  STEP 3 — DEFINE FEATURES & TARGETS
# ══════════════════════════════════════════════════════════════
print("\n🎯 Defining features and targets...")

# Features used to make predictions
FEATURES = [
    "category_enc",
    "uv_filter_type_enc",
    "filter_mechanism_enc",
    "photostable",
    "uva_protection",
    "uvb_protection",
    "eu_approved",
    "fda_approved",
    "skin_type_1_safe",
    "skin_type_2_safe",
    "skin_type_3_safe",
]

X = df[FEATURES]

# We train 2 models:
# 1. concern_level classifier → predicts None/Low/Medium/High
# 2. overall_score regressor  → predicts 1-10 score

y_concern = df["concern_level_enc"]
y_score   = df["overall_score"]

print(f"   Features: {FEATURES}")
print(f"   Samples:  {len(X)}")

# ══════════════════════════════════════════════════════════════
#  STEP 4 — TRAIN / TEST SPLIT
# ══════════════════════════════════════════════════════════════
print("\n✂️  Splitting data (80% train / 20% test)...")

X_train, X_test, yc_train, yc_test, ys_train, ys_test = train_test_split(
    X, y_concern, y_score,
    test_size=0.2, random_state=42
)

print(f"   Train: {len(X_train)} samples")
print(f"   Test:  {len(X_test)} samples")

# ══════════════════════════════════════════════════════════════
#  STEP 5 — TRAIN MODELS
# ══════════════════════════════════════════════════════════════
print("\n🌲 Training Random Forest models...")

# Model 1 — Concern Level Classifier
clf_concern = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_split=2,
    random_state=42,
    class_weight="balanced"
)
clf_concern.fit(X_train, yc_train)

# Model 2 — Overall Score Regressor
from sklearn.ensemble import RandomForestRegressor
clf_score = RandomForestRegressor(
    n_estimators=200,
    max_depth=10,
    random_state=42
)
clf_score.fit(X_train, ys_train)

print("   ✅ Models trained!")

# ══════════════════════════════════════════════════════════════
#  STEP 6 — EVALUATE
# ══════════════════════════════════════════════════════════════
print("\n📊 Evaluation Results:")
print("-" * 40)

# Concern classifier accuracy
yc_pred = clf_concern.predict(X_test)
acc = accuracy_score(yc_test, yc_pred)
print(f"\n   Concern Level Classifier Accuracy: {acc*100:.1f}%")
print("\n   Classification Report:")
concern_labels = [str(c) for c in label_encoders["concern_level"].classes_]
print(classification_report(yc_test, yc_pred,
      target_names=concern_labels, zero_division=0))

# Score regressor
ys_pred = clf_score.predict(X_test)
mae = np.mean(np.abs(ys_pred - ys_test))
print(f"   Score Regressor MAE: {mae:.2f} points (out of 10)")

# Feature importance
print("\n   🔍 Top Feature Importances (Concern Model):")
importances = clf_concern.feature_importances_
for feat, imp in sorted(zip(FEATURES, importances),
                         key=lambda x: -x[1])[:6]:
    bar = "█" * int(imp * 40)
    print(f"   {feat:<35} {bar} {imp:.3f}")

# ══════════════════════════════════════════════════════════════
#  STEP 7 — SAVE MODEL
# ══════════════════════════════════════════════════════════════
print("\n💾 Saving model...")

model_bundle = {
    "clf_concern":     clf_concern,
    "clf_score":       clf_score,
    "label_encoders":  label_encoders,
    "features":        FEATURES,
    "df":              df,   # ingredient lookup table
    "version":         "1.0",
}

with open(MODEL_PATH, "wb") as f:
    pickle.dump(model_bundle, f)

size_kb = os.path.getsize(MODEL_PATH) / 1024
print(f"   ✅ model.pkl saved ({size_kb:.0f} KB)")
print(f"   📍 Location: {MODEL_PATH}")

print("\n" + "=" * 55)
print("  ✅ Training complete! Run the app to use your model.")
print("=" * 55)