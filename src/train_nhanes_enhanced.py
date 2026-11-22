import pandas as pd
import numpy as np
import time
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report, confusion_matrix, recall_score, precision_score

start_time = time.time()
print("=========================================================================")
print("  NEFROAI-X: TRAINING ON BIG CLINICAL DATASET (CDC NHANES - 5,063 ADULTS)")
print("=========================================================================")

# 1. Load data
data_path = "datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv"
df = pd.read_csv(data_path)
print(f"[*] Total participants surveyed: {len(df):,}")

# 2. Filter adult patients with complete kidney tests (Age >= 18, Creatinine, uACR)
adults = df[(df["age_years"] >= 18) & df["serum_creatinine"].notna() & df["uacr"].notna()].copy()
print(f"[*] Valid adult cohort with full renal laboratory panel: {len(adults):,}")

# 3. Ground Truth: Official KDIGO 2021 CKD-EPI eGFR + Albuminuria (uACR)
is_female = (adults["sex_code"] == 2)
kappa = np.where(is_female, 0.7, 0.9)
alpha = np.where(is_female, -0.241, -0.302)
sex_mult = np.where(is_female, 1.012, 1.0)
ratio = adults["serum_creatinine"] / kappa
egfr = 142 * np.power(np.minimum(ratio, 1.0), alpha) * np.power(np.maximum(ratio, 1.0), -1.2) * np.power(0.9938, adults["age_years"]) * sex_mult

# Target label: 1 if CKD (eGFR < 60 or uACR >= 30), 0 if healthy
y = ((egfr < 60) | (adults["uacr"] >= 30)).astype(int)
print(f"[*] Clinical Class Breakdown: Healthy = {sum(y==0):,} ({sum(y==0)/len(y)*100:.1f}%), CKD At-Risk = {sum(y==1):,} ({sum(y==1)/len(y)*100:.1f}%)")

# 4. Feature Engineering: Clinical Biomarkers & Domain Interaction Ratios
adults["bun_cr_ratio"] = adults["blood_urea_nitrogen"] / (adults["serum_creatinine"] + 1e-4)

feature_cols = [
    "age_years",
    "sex_code",
    "serum_creatinine",
    "blood_urea_nitrogen",
    "bun_cr_ratio",
    "serum_glucose",
    "sodium",
    "potassium"
]

X = adults[feature_cols].copy()
X = X.fillna(X.median())

# 5. Stratified Split 80% Train, 20% Test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)
print(f"[*] Training partition: {len(X_train):,} patients | Hold-out test partition: {len(X_test):,} patients\n")

# 6. Train Random Forest Classifier
t0 = time.time()
rf = RandomForestClassifier(n_estimators=150, max_depth=10, class_weight="balanced", random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
rf_time = time.time() - t0

rf_preds = rf.predict(X_test)
rf_probs = rf.predict_proba(X_test)[:, 1]

print(f"[+] Model 1: Random Forest Classifier (Trained in {rf_time:.2f} seconds)")
print(f"    - Accuracy: {accuracy_score(y_test, rf_preds) * 100:.2f}%")
print(f"    - ROC-AUC:  {roc_auc_score(y_test, rf_probs):.4f}")

# 7. Train Gradient Boosting Classifier
t1 = time.time()
gb = GradientBoostingClassifier(n_estimators=150, max_depth=5, learning_rate=0.08, random_state=42)
gb.fit(X_train, y_train)
gb_time = time.time() - t1

gb_preds = gb.predict(X_test)
gb_probs = gb.predict_proba(X_test)[:, 1]

print(f"\n[+] Model 2: Gradient Boosting Classifier (Trained in {gb_time:.2f} seconds)")
print(f"    - Accuracy: {accuracy_score(y_test, gb_preds) * 100:.2f}%")
print(f"    - ROC-AUC:  {roc_auc_score(y_test, gb_probs):.4f}")

# 8. Clinical Calibration: Operating Threshold Tuning
print("\n-------------------------------------------------------------------------")
print("  CLINICAL RISK THRESHOLD TUNING (Operating Curve)")
print("-------------------------------------------------------------------------")
best_thresh = 0.50
best_f1 = 0
for thresh in [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
    cal_preds = (gb_probs >= thresh).astype(int)
    rec = recall_score(y_test, cal_preds)
    prec = precision_score(y_test, cal_preds)
    acc = accuracy_score(y_test, cal_preds)
    f1 = 2 * (prec * rec) / (prec + rec + 1e-6)
    print(f"  Threshold >= {thresh:.2f}  -->  Accuracy: {acc*100:.1f}% | Sensitivity: {rec*100:.1f}% | Precision: {prec*100:.1f}% | F1: {f1:.3f}")

total_elapsed = time.time() - start_time
print(f"\n[OK] Big Dataset Pipeline Finished Successfully in {total_elapsed:.2f} seconds total!")
print("=========================================================================")
