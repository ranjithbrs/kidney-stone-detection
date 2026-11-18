"""
=============================================================================
NEFROAI-CLEAN: Chronic Kidney Disease (CKD) Early Risk Screening Model
=============================================================================
Dataset: CDC NHANES (National Health and Nutrition Examination Survey)
Purpose: Screen for early kidney damage using routine clinical checkup tests
         (Age, Sex, Blood Sugar, Blood Urea, Sodium, Potassium).
=============================================================================
"""

import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report, confusion_matrix


# ---------------------------------------------------------------------------
# 1. LOAD THE DATASET
# ---------------------------------------------------------------------------
print("Loading CDC NHANES clinical dataset...")
data_path = "datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv"
df = pd.read_csv(data_path)

print(f"Total raw participants in survey: {len(df)}")


# ---------------------------------------------------------------------------
# 2. FILTER ADULT PATIENTS (Age >= 18) WITH VALID KIDNEY TESTS
# ---------------------------------------------------------------------------
# In clinical guidelines (KDIGO), adult eGFR formulas only apply to age >= 18.
adults = df[(df["age_years"] >= 18) & df["serum_creatinine"].notna() & df["uacr"].notna()].copy()
print(f"Adults with complete clinical lab records: {len(adults)}")


# ---------------------------------------------------------------------------
# 3. DEFINE THE GROUND-TRUTH MEDICAL TARGET (Label: 0 = Healthy, 1 = CKD Risk)
# ---------------------------------------------------------------------------
# Official medical definition of CKD (KDIGO Guidelines):
# Either eGFR < 60 mL/min/1.73m2  OR  Urine Albumin-to-Creatinine Ratio (uACR) >= 30 mg/g.

# Race-free CKD-EPI 2021 eGFR equation:
is_female = (adults["sex_code"] == 2)
kappa = np.where(is_female, 0.7, 0.9)
alpha = np.where(is_female, -0.241, -0.302)
sex_mult = np.where(is_female, 1.012, 1.0)

ratio = adults["serum_creatinine"] / kappa
egfr = 142 * np.power(np.minimum(ratio, 1.0), alpha) * np.power(np.maximum(ratio, 1.0), -1.2) * np.power(0.9938, adults["age_years"]) * sex_mult

# The target label: 1 if kidney damage exists, 0 if healthy
y = ((egfr < 60) | (adults["uacr"] >= 30)).astype(int)

ckd_count = y.sum()
healthy_count = len(y) - ckd_count
print(f"Clinical Class Distribution -> Healthy (0): {healthy_count} ({healthy_count/len(y)*100:.1f}%), CKD Risk (1): {ckd_count} ({ckd_count/len(y)*100:.1f}%)")


# ---------------------------------------------------------------------------
# 4. SELECT THE SCREENING FEATURES (X)
# ---------------------------------------------------------------------------
# NOVELTY / NON-LEAKY DESIGN:
# We do NOT include serum_creatinine or uacr in the features!
# Why? Because creatinine is already used to define the label. Giving it to the model
# would be circular and cheat. Instead, we use general routine checkup labs:
feature_cols = [
    "age_years",           # Patient age
    "sex_code",            # 1 = Male, 2 = Female
    "serum_glucose",       # Random blood sugar (mg/dL)
    "blood_urea_nitrogen", # BUN (waste product filtered by kidneys, mg/dL)
    "sodium",              # Electrolyte balance (mmol/L)
    "potassium",           # Electrolyte balance (mmol/L)
]

X = adults[feature_cols].copy()
print(f"Features used for screening: {feature_cols}")


# ---------------------------------------------------------------------------
# 5. SPLIT INTO 80% TRAINING AND 20% TESTING (Stratified)
# ---------------------------------------------------------------------------
# Stratified split ensures both Train and Test have the exact same 18.6% CKD ratio.
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)
print(f"Training samples: {len(X_train)}, Testing samples: {len(X_test)}")


# ---------------------------------------------------------------------------
# 6. CLEANING & SCALING (Preprocessed strictly on Training data)
# ---------------------------------------------------------------------------
# Fill any missing values with the median of training data
imputer = SimpleImputer(strategy="median")
X_train_clean = imputer.fit_transform(X_train)
X_test_clean = imputer.transform(X_test)

# Scale numbers so all features are on a standard scale (mean=0, std=1)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train_clean)
X_test_scaled = scaler.transform(X_test_clean)


# ---------------------------------------------------------------------------
# 7. TRAIN THE MODELS
# ---------------------------------------------------------------------------
print("\n--- Training Model 1: Logistic Regression (Baseline) ---")
lr_model = LogisticRegression(class_weight="balanced", random_state=42)
lr_model.fit(X_train_scaled, y_train)

lr_preds = lr_model.predict(X_test_scaled)
lr_probs = lr_model.predict_proba(X_test_scaled)[:, 1]

print(f"Logistic Regression Accuracy: {accuracy_score(y_test, lr_preds) * 100:.2f}%")
print(f"Logistic Regression ROC-AUC:  {roc_auc_score(y_test, lr_probs):.4f}")


print("\n--- Training Model 2: Random Forest Classifier (Champion) ---")
# class_weight='balanced' tells the trees to pay equal attention to the rarer CKD class
rf_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=6,             # Keeps trees simple and prevents memorization/overfitting
    class_weight="balanced",
    random_state=42
)
rf_model.fit(X_train_clean, y_train)

rf_preds = rf_model.predict(X_test_clean)
rf_probs = rf_model.predict_proba(X_test_clean)[:, 1]

print(f"Random Forest Accuracy: {accuracy_score(y_test, rf_preds) * 100:.2f}%")
print(f"Random Forest ROC-AUC:  {roc_auc_score(y_test, rf_probs):.4f}")


# ---------------------------------------------------------------------------
# 8. DETAILED EVALUATION OF THE CHAMPION MODEL
# ---------------------------------------------------------------------------
print("\n================ Classification Report (Random Forest) ================")
print(classification_report(y_test, rf_preds, target_names=["Healthy (0)", "CKD Risk (1)"]))

cm = confusion_matrix(y_test, rf_preds)
print("Confusion Matrix:")
print(f"  True Negatives  (Healthy correctly predicted Healthy): {cm[0][0]}")
print(f"  False Positives (Healthy incorrectly predicted CKD):     {cm[0][1]}")
print(f"  False Negatives (CKD missed by model):                   {cm[1][0]}")
print(f"  True Positives  (CKD correctly caught by model):         {cm[1][1]}")


# ---------------------------------------------------------------------------
# 9. SAVE THE TRAINED MODEL ARTIFACT (For the website)
# ---------------------------------------------------------------------------
model_artifact = {
    "model": rf_model,
    "imputer": imputer,
    "feature_cols": feature_cols
}

import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))

save_path_models = os.path.join(project_root, "models", "nhanes_rf_model.pkl")
save_path_src = os.path.join(current_dir, "nhanes_rf_model.pkl")

joblib.dump(model_artifact, save_path_models)
joblib.dump(model_artifact, save_path_src)
print(f"\nTrained model successfully saved to: {save_path_models}")
print(f"Also saved to: {save_path_src}")
print("Done! You now have a working, real-world trained model.")
