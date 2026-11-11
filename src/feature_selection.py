"""
Phase 5: Feature Selection Module (NefroAI Implementation)
Implements:
1. Filter Methods: Mutual Information & ANOVA F-score
2. Embedded Method: Random Forest Feature Importance (Gini)
3. Wrapper Method: Recursive Feature Elimination (RFE)
4. Hybrid Feature Selection: Rank-Aggregation Consensus
5. Redundancy & Correlation Analysis
6. Comparative Performance Evaluation (Full Features vs Selected Subsets)
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif, f_classif, RFE
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import shap


class FeatureSelectionPipeline:
    def __init__(self, random_state=42):
        self.random_state = random_state

    def compute_mutual_info(self, X_train, y_train):
        """Filter Method 1: Mutual Information."""
        mi_scores = mutual_info_classif(X_train, y_train, random_state=self.random_state)
        return pd.Series(mi_scores, index=X_train.columns).sort_values(ascending=False)

    def compute_anova_f(self, X_train, y_train):
        """Filter Method 2: ANOVA F-test."""
        f_scores, _ = f_classif(X_train, y_train)
        f_scores = np.nan_to_num(f_scores, nan=0.0)
        return pd.Series(f_scores, index=X_train.columns).sort_values(ascending=False)

    def compute_rf_importance(self, X_train, y_train):
        """Embedded Method: Random Forest Gini Feature Importance."""
        rf = RandomForestClassifier(n_estimators=100, random_state=self.random_state)
        rf.fit(X_train, y_train)
        return pd.Series(rf.feature_importances_, index=X_train.columns).sort_values(ascending=False)

    def compute_rfe_ranking(self, X_train, y_train, n_features_to_select=10):
        """Wrapper Method: Recursive Feature Elimination with RF."""
        rf = RandomForestClassifier(n_estimators=100, random_state=self.random_state)
        rfe = RFE(estimator=rf, n_features_to_select=n_features_to_select, step=1)
        rfe.fit(X_train, y_train)
        ranking_series = pd.Series(rfe.ranking_, index=X_train.columns).sort_values(ascending=True)
        return ranking_series

    def compute_shap_importance(self, X_train, y_train):
        """Game-Theoretic TreeSHAP Mean |phi| Ranking on Training Data Only."""
        rf = RandomForestClassifier(n_estimators=100, random_state=self.random_state)
        rf.fit(X_train, y_train)
        explainer = shap.TreeExplainer(rf)
        sv = explainer(X_train)
        vals = sv.values[:, :, 1] if len(sv.values.shape) == 3 else sv.values
        mean_abs_shap = np.mean(np.abs(vals), axis=0)
        return pd.Series(mean_abs_shap, index=X_train.columns).sort_values(ascending=False)

    def run_hybrid_selection(self, X_train, y_train, top_k=10, include_shap=False):
        """
        Hybrid Selection:
        Normalizes ranks across Mutual Information, ANOVA F, Random Forest Importance,
        RFE, and (optionally) cooperative TreeSHAP importance.
        Computes consensus Borda score and selects top-K consensus biomarkers.
        """
        features = list(X_train.columns)

        # 1. Mutual Information Rank (1 = best)
        mi_s = self.compute_mutual_info(X_train, y_train)
        mi_ranks = {feat: rank for rank, feat in enumerate(mi_s.index, start=1)}

        # 2. ANOVA F Rank (1 = best)
        anova_s = self.compute_anova_f(X_train, y_train)
        anova_ranks = {feat: rank for rank, feat in enumerate(anova_s.index, start=1)}

        # 3. RF Importance Rank (1 = best)
        rf_s = self.compute_rf_importance(X_train, y_train)
        rf_ranks = {feat: rank for rank, feat in enumerate(rf_s.index, start=1)}

        # 4. RFE Rank (1 = best)
        rfe_s = self.compute_rfe_ranking(X_train, y_train, n_features_to_select=top_k)
        rfe_ranks = {feat: rank for rank, feat in enumerate(rfe_s.index, start=1)}

        # 5. Optional TreeSHAP Rank (1 = best)
        shap_s = self.compute_shap_importance(X_train, y_train) if include_shap else None
        shap_ranks = {feat: rank for rank, feat in enumerate(shap_s.index, start=1)} if shap_s is not None else {}

        # Combine into consensus DataFrame
        rank_records = []
        for feat in features:
            rank_sum = mi_ranks[feat] + anova_ranks[feat] + rf_ranks[feat] + rfe_ranks[feat]
            denom = 4.0
            if include_shap:
                rank_sum += shap_ranks[feat]
                denom = 5.0
            avg_rank = rank_sum / denom
            rec = {
                "feature": feat,
                "mi_score": round(float(mi_s.get(feat, 0)), 4),
                "anova_f_score": round(float(anova_s.get(feat, 0)), 2),
                "rf_importance": round(float(rf_s.get(feat, 0)), 4),
                "rfe_rank": int(rfe_ranks[feat]),
                "consensus_rank_score": round(float(avg_rank), 2)
            }
            if include_shap and shap_s is not None:
                rec["shap_mean_abs"] = round(float(shap_s.get(feat, 0)), 4)
                rec["shap_rank"] = int(shap_ranks[feat])
            rank_records.append(rec)

        df_rankings = pd.DataFrame(rank_records).sort_values(by="consensus_rank_score", ascending=True)
        df_rankings["final_rank"] = range(1, len(df_rankings) + 1)

        selected_features = list(df_rankings.head(top_k)["feature"])
        return df_rankings, selected_features

    def evaluate_cv_selection_stability(self, dataset_path="datasets/clinical/dataset_A_uci_ckd.csv", top_k=10, n_splits=5):
        """Run 5-method (MI+ANOVA+RF+RFE+SHAP) feature selection strictly inside training folds.

        Never touches the 20% held-out test set. Returns per-fold selections,
        pairwise Jaccard similarity stability, and biomarker selection frequencies.
        """
        try:
            from src.preprocessing import ClinicalDataPreprocessor
        except ImportError:
            from preprocessing import ClinicalDataPreprocessor

        raw_df = pd.read_csv(dataset_path)
        prep_helper = ClinicalDataPreprocessor(target_col="classification", apply_smote=True, random_state=self.random_state)
        clean_df = prep_helper._sanitize_raw_df(raw_df)
        y = clean_df["classification"].astype(str).str.strip().str.lower().map({"ckd": 1, "notckd": 0, "1": 1, "0": 0})
        if y.isnull().any():
            y = y.fillna(y.mode()[0])
        y = y.astype(int)
        X = clean_df.drop(columns=["classification"])

        X_train_raw, _, y_train_raw, _ = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=self.random_state
        )

        num_cols = list(X_train_raw.select_dtypes(include=[np.number]).columns)
        cat_cols = list(X_train_raw.select_dtypes(exclude=[np.number]).columns)
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)

        fold_sets = []
        freq_counts = {}
        for tr_idx, _ in skf.split(X_train_raw, y_train_raw):
            fold_prep = ClinicalDataPreprocessor(target_col="classification", apply_smote=True, random_state=self.random_state)
            fold_prep.num_cols, fold_prep.cat_cols, fold_prep.feature_names = num_cols, cat_cols, num_cols + cat_cols
            X_tr_arr = fold_prep._fit_transform_features(X_train_raw.iloc[tr_idx])
            y_tr_arr = np.asarray(y_train_raw.iloc[tr_idx], dtype=int)
            X_tr_res, y_tr_res = fold_prep.smote.fit_resample(X_tr_arr, y_tr_arr)
            X_tr_df = pd.DataFrame(X_tr_res, columns=fold_prep.feature_names)
            _, sel_feats = self.run_hybrid_selection(X_tr_df, y_tr_res, top_k=top_k, include_shap=True)
            fold_sets.append(sel_feats)
            for f in sel_feats:
                freq_counts[f] = freq_counts.get(f, 0) + 1

        jaccards = []
        for i in range(len(fold_sets)):
            for j in range(i + 1, len(fold_sets)):
                s1, s2 = set(fold_sets[i]), set(fold_sets[j])
                jaccards.append(len(s1 & s2) / len(s1 | s2))

        mean_jaccard = round(float(np.mean(jaccards)), 4) if jaccards else 1.0
        stable_features = [
            f for f, cnt in sorted(freq_counts.items(), key=lambda x: (-x[1], x[0]))
        ]
        return {
            "n_splits": n_splits,
            "top_k": top_k,
            "train_partition_size": len(X_train_raw),
            "held_out_test_excluded": True,
            "mean_pairwise_jaccard": mean_jaccard,
            "fold_selections": fold_sets,
            "feature_frequencies": dict(sorted(freq_counts.items(), key=lambda x: (-x[1], x[0]))),
            "consensus_by_frequency": stable_features[:top_k],
        }

    def analyze_redundancy(self, X_train, threshold=0.80):
        """Identifies highly correlated / collinear redundant feature pairs."""
        corr_matrix = X_train.corr().abs()
        upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        
        redundant_pairs = []
        for col in upper_tri.columns:
            high_corr_rows = upper_tri[col][upper_tri[col] >= threshold]
            for row, val in high_corr_rows.items():
                redundant_pairs.append({
                    "feature_1": row,
                    "feature_2": col,
                    "correlation": round(float(val), 4)
                })
        return redundant_pairs


def evaluate_feature_subsets(X_train, X_test, y_train, y_test, feature_subsets):
    """
    Evaluates baseline models across different feature subsets:
    (Full vs Filter vs Wrapper vs Hybrid)
    """
    models = {
        "Random_Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "Logistic_Regression": LogisticRegression(max_iter=1000, random_state=42),
        "Decision_Tree": DecisionTreeClassifier(random_state=42),
        "Support_Vector_Machine": SVC(probability=True, random_state=42),
        "K_Nearest_Neighbors": KNeighborsClassifier(n_neighbors=5)
    }

    results = {}
    for subset_name, feats in feature_subsets.items():
        results[subset_name] = {
            "num_features": len(feats),
            "features": feats,
            "models": {}
        }
        X_tr_sub = X_train[feats]
        X_te_sub = X_test[feats]

        for m_name, model in models.items():
            model.fit(X_tr_sub, y_train)
            y_pred = model.predict(X_te_sub)
            if hasattr(model, "predict_proba"):
                y_prob = model.predict_proba(X_te_sub)[:, 1]
            else:
                y_prob = y_pred

            acc = accuracy_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred, zero_division=0)
            rec = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            try:
                auc = roc_auc_score(y_test, y_prob)
            except Exception:
                auc = float('nan')

            results[subset_name]["models"][m_name] = {
                "accuracy": round(float(acc), 4),
                "precision": round(float(prec), 4),
                "recall": round(float(rec), 4),
                "f1_score": round(float(f1), 4),
                "roc_auc": round(float(auc), 4)
            }

    return results


def main():
    os.makedirs("runs/feature_selection", exist_ok=True)
    os.makedirs("models/feature_selected", exist_ok=True)

    pipeline = FeatureSelectionPipeline(random_state=42)

    # -------------------------------------------------------------
    # 1. DATASET A (UCI Chronic Kidney Disease)
    # -------------------------------------------------------------
    print("=" * 60)
    print("PHASE 5: FEATURE SELECTION FOR DATASET A (UCI CKD)")
    print("=" * 60)

    X_train_A = pd.read_csv("datasets/processed/Dataset_A_X_train.csv")
    X_test_A = pd.read_csv("datasets/processed/Dataset_A_X_test.csv")
    y_train_A = pd.read_csv("datasets/processed/Dataset_A_y_train.csv").values.ravel()
    y_test_A = pd.read_csv("datasets/processed/Dataset_A_y_test.csv").values.ravel()

    # Redundancy Analysis
    redundant_A = pipeline.analyze_redundancy(X_train_A, threshold=0.75)
    print(f"\n[Dataset A] Highly correlated pairs (r >= 0.75): {len(redundant_A)}")
    for pair in redundant_A:
        print(f"  -> {pair['feature_1']} & {pair['feature_2']}: r = {pair['correlation']}")

    # Hybrid Feature Selection (select top 10 features as per NefroAI)
    rankings_A, hybrid_top10_A = pipeline.run_hybrid_selection(X_train_A, y_train_A, top_k=10)
    print(f"\n[Dataset A] Top 10 Hybrid Selected Features:")
    for i, row in rankings_A.head(10).iterrows():
        print(f"  #{row['final_rank']}: {row['feature']} (Consensus Rank: {row['consensus_rank_score']}, MI: {row['mi_score']}, RF: {row['rf_importance']})")

    # Define feature subsets to compare
    mi_top10_A = list(pipeline.compute_mutual_info(X_train_A, y_train_A).head(10).index)
    rfe_top10_A = list(pipeline.compute_rfe_ranking(X_train_A, y_train_A, n_features_to_select=10).head(10).index)
    subsets_A = {
        "Full_Features (24)": list(X_train_A.columns),
        "Mutual_Info_Filter (10)": mi_top10_A,
        "RFE_Wrapper (10)": rfe_top10_A,
        "Hybrid_Consensus (10)": hybrid_top10_A
    }

    # Comparative Performance
    comparison_A = evaluate_feature_subsets(X_train_A, X_test_A, y_train_A, y_test_A, subsets_A)

    # -------------------------------------------------------------
    # 2. DATASET B (Kidney Stone Urinalysis)
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PHASE 5: FEATURE SELECTION FOR DATASET B (KIDNEY STONE)")
    print("=" * 60)

    X_train_B = pd.read_csv("datasets/processed/Dataset_B_X_train.csv")
    X_test_B = pd.read_csv("datasets/processed/Dataset_B_X_test.csv")
    y_train_B = pd.read_csv("datasets/processed/Dataset_B_y_train.csv").values.ravel()
    y_test_B = pd.read_csv("datasets/processed/Dataset_B_y_test.csv").values.ravel()

    redundant_B = pipeline.analyze_redundancy(X_train_B, threshold=0.75)
    print(f"\n[Dataset B] Highly correlated pairs: {len(redundant_B)}")
    for pair in redundant_B:
        print(f"  -> {pair['feature_1']} & {pair['feature_2']}: r = {pair['correlation']}")

    rankings_B, hybrid_top4_B = pipeline.run_hybrid_selection(X_train_B, y_train_B, top_k=4)
    print(f"\n[Dataset B] Top 4 Hybrid Selected Features:")
    for i, row in rankings_B.head(4).iterrows():
        print(f"  #{row['final_rank']}: {row['feature']} (Consensus Rank: {row['consensus_rank_score']}, MI: {row['mi_score']}, RF: {row['rf_importance']})")

    subsets_B = {
        "Full_Features (6)": list(X_train_B.columns),
        "Hybrid_Consensus (4)": hybrid_top4_B
    }
    comparison_B = evaluate_feature_subsets(X_train_B, X_test_B, y_train_B, y_test_B, subsets_B)

    # -------------------------------------------------------------
    # 3. SAVE RECORDED RESULTS
    # -------------------------------------------------------------
    selection_records = {
        "Dataset_A": {
            "redundant_pairs": redundant_A,
            "full_rankings": rankings_A.to_dict(orient="records"),
            "selected_features": {
                "hybrid_top10": hybrid_top10_A,
                "mi_top10": mi_top10_A,
                "rfe_top10": rfe_top10_A
            },
            "performance_comparison": comparison_A
        },
        "Dataset_B": {
            "redundant_pairs": redundant_B,
            "full_rankings": rankings_B.to_dict(orient="records"),
            "selected_features": {
                "hybrid_top4": hybrid_top4_B
            },
            "performance_comparison": comparison_B
        }
    }

    with open("runs/feature_selection/selected_features.json", "w") as f:
        json.dump(selection_records, f, indent=2)
    print("\n[OK] Saved runs/feature_selection/selected_features.json")

    # Generate Markdown Report
    md = "# Feature Selection & Model Performance Comparison Report\n\n"
    md += "This report analyzes the individual and hybrid feature selection techniques applied to the clinical datasets as described in the **NefroAI** paper.\n\n"
    
    md += "## 1. Dataset A (UCI Chronic Kidney Disease)\n\n"
    md += "### Top 10 Consensus Biomarkers (Hybrid Feature Selection)\n"
    md += "| Rank | Feature | Description | Consensus Rank Score | Mutual Info | RF Gini Importance |\n"
    md += "| :---: | :--- | :--- | :---: | :---: | :---: |\n"
    
    desc_map_A = {
        "hemo": "Hemoglobin (g/dL)",
        "sg": "Specific Gravity",
        "sc": "Serum Creatinine (mg/dL)",
        "pcv": "Packed Cell Volume (%)",
        "al": "Albumin",
        "rc": "Red Blood Cell Count",
        "bgr": "Blood Glucose Random (mg/dL)",
        "bu": "Blood Urea (mg/dL)",
        "htn": "Hypertension",
        "dm": "Diabetes Mellitus",
        "sod": "Sodium (mEq/L)",
        "age": "Patient Age",
        "bp": "Blood Pressure (mm/Hg)",
        "pe": "Pedal Edema",
        "appet": "Appetite",
        "pc": "Pus Cell",
        "rbc": "Red Blood Cells",
        "su": "Sugar",
        "pot": "Potassium",
        "wc": "White Blood Cell Count",
        "ane": "Anemia",
        "cad": "Coronary Artery Disease",
        "pcc": "Pus Cell Clumps",
        "ba": "Bacteria"
    }

    for i, row in rankings_A.head(10).iterrows():
        f_name = row["feature"]
        md += f"| **#{row['final_rank']}** | `{f_name}` | {desc_map_A.get(f_name, f_name)} | {row['consensus_rank_score']} | {row['mi_score']} | {row['rf_importance']} |\n"

    md += "\n### Redundancy & Collinearity Findings (Dataset A)\n"
    for pair in redundant_A:
        md += f"- **`{pair['feature_1']}` & `{pair['feature_2']}`**: Pearson $r = {pair['correlation']}$. (*Physiological reason*: Hemoglobin and Packed Cell Volume both directly measure red blood cell volume/oxygen carrying capacity; one can serve as a surrogate for the other).\n"

    md += "\n### Performance Comparison: Full 24 Features vs Selected Top 10 Subsets\n\n"
    md += "| Model | Full 24 Features (Acc / F1 / AUC) | Hybrid Top 10 (Acc / F1 / AUC) | MI Filter Top 10 (Acc / F1 / AUC) | RFE Wrapper Top 10 (Acc / F1 / AUC) |\n"
    md += "| :--- | :---: | :---: | :---: | :---: |\n"

    for m_name in comparison_A["Full_Features (24)"]["models"]:
        m_full = comparison_A["Full_Features (24)"]["models"][m_name]
        m_hyb = comparison_A["Hybrid_Consensus (10)"]["models"][m_name]
        m_mi = comparison_A["Mutual_Info_Filter (10)"]["models"][m_name]
        m_rfe = comparison_A["RFE_Wrapper (10)"]["models"][m_name]

        formatted_name = m_name.replace("_", " ")
        md += (
            f"| **{formatted_name}** | {m_full['accuracy']*100:.1f}% / {m_full['f1_score']:.3f} / {m_full['roc_auc']:.3f} | "
            f"**{m_hyb['accuracy']*100:.1f}% / {m_hyb['f1_score']:.3f} / {m_hyb['roc_auc']:.3f}** | "
            f"{m_mi['accuracy']*100:.1f}% / {m_mi['f1_score']:.3f} / {m_mi['roc_auc']:.3f} | "
            f"{m_rfe['accuracy']*100:.1f}% / {m_rfe['f1_score']:.3f} / {m_rfe['roc_auc']:.3f} |\n"
        )

    md += "\n---\n\n## 2. Dataset B (Kidney Stone Urinalysis)\n\n"
    md += "### Top Selected Urinalysis Indicators\n"
    md += "| Rank | Feature | Description | Consensus Score | MI Score | RF Importance |\n"
    md += "| :---: | :--- | :--- | :---: | :---: | :---: |\n"
    
    desc_map_B = {
        "calc": "Calcium concentration (mmol/L)",
        "gravity": "Urine Specific Gravity",
        "cond": "Conductivity (mMho)",
        "osmo": "Osmolality (mOsm)",
        "urea": "Urea concentration (mmol/L)",
        "ph": "Urine pH"
    }

    for i, row in rankings_B.head(4).iterrows():
        f_name = row["feature"]
        md += f"| **#{row['final_rank']}** | `{f_name}` | {desc_map_B.get(f_name, f_name)} | {row['consensus_rank_score']} | {row['mi_score']} | {row['rf_importance']} |\n"

    md += "\n### Performance Comparison: Full 6 Features vs Hybrid Top 4 (Dataset B)\n\n"
    md += "| Model | Full 6 Features (Acc / F1 / AUC) | Hybrid Top 4 Features (Acc / F1 / AUC) |\n"
    md += "| :--- | :---: | :---: |\n"

    for m_name in comparison_B["Full_Features (6)"]["models"]:
        m_full = comparison_B["Full_Features (6)"]["models"][m_name]
        m_hyb = comparison_B["Hybrid_Consensus (4)"]["models"][m_name]
        formatted_name = m_name.replace("_", " ")
        md += (
            f"| **{formatted_name}** | {m_full['accuracy']*100:.1f}% / {m_full['f1_score']:.3f} / {m_full['roc_auc']:.3f} | "
            f"**{m_hyb['accuracy']*100:.1f}% / {m_hyb['f1_score']:.3f} / {m_hyb['roc_auc']:.3f}** |\n"
        )

    with open("runs/feature_selection/feature_selection_report.md", "w") as f:
        f.write(md)
    print("[OK] Saved runs/feature_selection/feature_selection_report.md")


if __name__ == "__main__":
    main()
