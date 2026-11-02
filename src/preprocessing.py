"""
Reusable, leak-free preprocessing pipeline for clinical tabular datasets
(NefroAI Framework Implementation)
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.impute import SimpleImputer
from imblearn.over_sampling import SMOTE


class ClinicalDataPreprocessor:
    """
    Standardized, leak-proof preprocessor for clinical datasets.
    - Fits imputers and scalers strictly on training data
    - Transforms test data without leakage
    - Applies SMOTE class balancing exclusively to training splits
    - Serializes pipeline state for production inference
    """

    def __init__(self, target_col='classification', scale_type='standard', apply_smote=True, random_state=42):
        self.target_col = target_col
        self.scale_type = scale_type
        self.apply_smote = apply_smote
        self.random_state = random_state

        self.num_cols = []
        self.cat_cols = []
        self.feature_names = []
        
        self.num_imputer = SimpleImputer(strategy='median')
        self.cat_imputer = SimpleImputer(strategy='most_frequent')
        self.scaler = StandardScaler() if scale_type == 'standard' else MinMaxScaler()
        self.smote = SMOTE(random_state=random_state)
        self.cat_mappings = {}
        self.target_mapping = {}

    def _sanitize_raw_df(self, df):
        """Sanitizes raw DataFrame: strips whitespace, rogue tabs, coerces numeric fields."""
        data = df.copy()

        # Drop identifier or row-number columns
        for col in ['id', 'Unnamed: 0']:
            if col in data.columns:
                data = data.drop(columns=[col])

        # Strip strings and clean rogue tab characters
        for col in data.columns:
            if data[col].dtype == object:
                data[col] = data[col].astype(str).str.strip().str.replace('\t', '')
                # Replace '?' or empty strings with NaN
                data[col] = data[col].replace(['?', '', 'nan', 'None'], np.nan)

        # Certain columns in CKD datasets should be numeric but often contain string artifacts
        potential_num = ['age', 'bp', 'sg', 'al', 'su', 'bgr', 'bu', 'sc', 'sod', 'pot', 'hemo', 'pcv', 'wc', 'rc',
                         'gravity', 'ph', 'osmo', 'cond', 'urea', 'calc']
        for col in potential_num:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

        return data

    def prepare_data(self, file_path_or_df, test_size=0.2):
        """
        Loads raw data, sanitizes it, separates features and target,
        performs stratified train/test split, and applies leak-free transformations.
        """
        if isinstance(file_path_or_df, str):
            raw_df = pd.read_csv(file_path_or_df)
        else:
            raw_df = file_path_or_df.copy()

        clean_df = self._sanitize_raw_df(raw_df)

        # Locate target column
        if self.target_col not in clean_df.columns:
            for cand in ['classification', 'class', 'target']:
                if cand in clean_df.columns:
                    self.target_col = cand
                    break

        if self.target_col not in clean_df.columns:
            raise ValueError(f"Target column '{self.target_col}' not found in data.")

        # Clean target labels
        y_raw = clean_df[self.target_col].copy()
        if y_raw.dtype == object:
            y_raw = y_raw.astype(str).str.strip().str.lower()
            # Map common binary categories: ckd->1, notckd->0
            self.target_mapping = {'ckd': 1, 'notckd': 0, '1': 1, '0': 0, 'true': 1, 'false': 0}
            y = y_raw.map(self.target_mapping)
            # Impute any missing target with mode if needed
            if y.isnull().any():
                y = y.fillna(y.mode()[0])
            y = y.astype(int)
        else:
            y = y_raw.astype(int)

        X = clean_df.drop(columns=[self.target_col])

        # Identify numerical and categorical columns
        self.num_cols = list(X.select_dtypes(include=[np.number]).columns)
        self.cat_cols = list(X.select_dtypes(exclude=[np.number]).columns)
        self.feature_names = self.num_cols + self.cat_cols

        # 1. Stratified Train-Test Split (PREVENT LEAKAGE BEFORE ANY IMPUTATION / SCALING)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, stratify=y, random_state=self.random_state
        )

        # 2. Imputation: Fit strictly on X_train, transform both
        X_train_proc = self._fit_transform_features(X_train)
        X_test_proc = self._transform_features(X_test)

        # 3. Class Imbalance: Apply SMOTE strictly on X_train_proc, y_train
        if self.apply_smote and len(np.unique(y_train)) > 1:
            try:
                X_train_final, y_train_final = self.smote.fit_resample(X_train_proc, y_train)
            except Exception as e:
                print(f"[Warning] SMOTE skipped: {e}")
                X_train_final, y_train_final = X_train_proc, y_train
        else:
            X_train_final, y_train_final = X_train_proc, y_train

        # Convert back to DataFrame with feature names for interpretability
        X_train_df = pd.DataFrame(X_train_final, columns=self.feature_names)
        X_test_df = pd.DataFrame(X_test_proc, columns=self.feature_names)

        return X_train_df, X_test_df, y_train_final, y_test

    def _fit_transform_features(self, X_train):
        """Fits imputers and scaler on training features, then transforms them."""
        # Numerical pipeline
        if self.num_cols:
            num_data = self.num_imputer.fit_transform(X_train[self.num_cols])
            num_scaled = self.scaler.fit_transform(num_data)
        else:
            num_scaled = np.empty((len(X_train), 0))

        # Categorical pipeline
        if self.cat_cols:
            cat_data = self.cat_imputer.fit_transform(X_train[self.cat_cols])
            cat_encoded = np.zeros_like(cat_data, dtype=float)
            for i, col in enumerate(self.cat_cols):
                # Build deterministic category mapping from training data
                unique_vals = sorted(list(set(cat_data[:, i])))
                mapping = {val: idx for idx, val in enumerate(unique_vals)}
                self.cat_mappings[col] = mapping
                cat_encoded[:, i] = [mapping.get(v, 0) for v in cat_data[:, i]]
        else:
            cat_encoded = np.empty((len(X_train), 0))

        if self.num_cols and self.cat_cols:
            return np.hstack([num_scaled, cat_encoded])
        elif self.num_cols:
            return num_scaled
        else:
            return cat_encoded

    def _transform_features(self, X_test):
        """Transforms test features using fitted training imputers, scalers, and mappings."""
        # Numerical
        if self.num_cols:
            num_data = self.num_imputer.transform(X_test[self.num_cols])
            num_scaled = self.scaler.transform(num_data)
        else:
            num_scaled = np.empty((len(X_test), 0))

        # Categorical
        if self.cat_cols:
            cat_data = self.cat_imputer.transform(X_test[self.cat_cols])
            cat_encoded = np.zeros_like(cat_data, dtype=float)
            for i, col in enumerate(self.cat_cols):
                mapping = self.cat_mappings.get(col, {})
                cat_encoded[:, i] = [mapping.get(v, 0) for v in cat_data[:, i]]
        else:
            cat_encoded = np.empty((len(X_test), 0))

        if self.num_cols and self.cat_cols:
            return np.hstack([num_scaled, cat_encoded])
        elif self.num_cols:
            return num_scaled
        else:
            return cat_encoded

    def transform_single_record(self, record_dict):
        """Transforms a single incoming patient record (dictionary) for real-time inference."""
        df = pd.DataFrame([record_dict])
        return self.transform_df(df)

    def transform_df(self, df):
        """Transforms a multi-record DataFrame in a single vectorized batch operation."""
        df_copy = df.copy()
        df_sanitized = self._sanitize_raw_df(df_copy)
        # Ensure all expected columns exist
        for col in self.num_cols + self.cat_cols:
            if col not in df_sanitized.columns:
                df_sanitized[col] = np.nan
        transformed_array = self._transform_features(df_sanitized)
        return pd.DataFrame(transformed_array, columns=self.feature_names)

    def save_pipeline(self, output_path):
        """Serializes the fitted pipeline to a file."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        joblib.dump(self, output_path)
        print(f"Preprocessor pipeline successfully saved to: {output_path}")

    @staticmethod
    def load_pipeline(pipeline_path):
        """Loads a pre-trained serialized pipeline."""
        return joblib.load(pipeline_path)
