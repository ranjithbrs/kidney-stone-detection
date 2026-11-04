"""Random Survival Forest (RSF) candidate architecture for Engine 3.

Provides a tree-ensemble survival analysis implementation handling right-censored outcomes
via log-rank splitting criteria and Nelson-Aalen / Kaplan-Meier leaf hazard estimators.

Clinical & Scientific Guardrails:
- Random Survival Forest models non-linear interactions and non-proportional hazards,
  but requires larger sample sizes than Cox PH to avoid overfitting.
- RSF MUST NOT be claimed as clinically superior to Cox PH without empirical evaluation
  on an independent real-world cohort (e.g. CRIC).
- RSF is a candidate architecture; it must NOT be fitted on synthetic simulator data.
- Feature importance is calculated strictly via out-of-bag (OOB) permutation importance.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


@dataclass
class RSFConfig:
    """Reproducible configuration for Random Survival Forest training.

    Attributes:
        n_estimators: Number of survival trees in the ensemble.
        max_depth: Maximum tree depth to constrain complexity.
        min_samples_split: Minimum node size required to evaluate a split.
        min_samples_leaf: Minimum samples required in each leaf node.
        max_features: Number of features to consider per split ('sqrt', 'log2', or int).
        random_state: Explicit random seed for bagging and feature subsampling.
    """

    n_estimators: int = 50
    max_depth: Optional[int] = 5
    min_samples_split: int = 10
    min_samples_leaf: int = 5
    max_features: Union[str, int, float] = "sqrt"
    random_state: int = 42


class _SurvivalTreeNode:
    """Node in an individual survival tree."""

    def __init__(
        self,
        depth: int = 0,
        is_leaf: bool = False,
        feature_idx: Optional[int] = None,
        threshold: Optional[float] = None,
        left: Optional["_SurvivalTreeNode"] = None,
        right: Optional["_SurvivalTreeNode"] = None,
        event_times: Optional[np.ndarray] = None,
        leaf_survival: Optional[np.ndarray] = None,
        leaf_cum_hazard: Optional[np.ndarray] = None,
    ):
        self.depth = depth
        self.is_leaf = is_leaf
        self.feature_idx = feature_idx
        self.threshold = threshold
        self.left = left
        self.right = right
        self.event_times = event_times
        self.leaf_survival = leaf_survival
        self.leaf_cum_hazard = leaf_cum_hazard

    def predict_survival_at(self, t: float) -> float:
        """Evaluate leaf Kaplan-Meier survival at time horizon t."""
        if self.event_times is None or len(self.event_times) == 0:
            return 1.0
        if t < self.event_times[0]:
            return 1.0
        idx = np.searchsorted(self.event_times, t, side="right") - 1
        return float(self.leaf_survival[idx])


class _SurvivalTree:
    """Single survival tree using log-rank test statistic for binary splitting."""

    def __init__(self, config: RSFConfig, seed: int):
        self.config = config
        self.rng = np.random.default_rng(seed)
        self.root: Optional[_SurvivalTreeNode] = None

    def fit(self, X: np.ndarray, durations: np.ndarray, events: np.ndarray) -> "_SurvivalTree":
        self.root = self._build_node(X, durations, events, depth=0)
        return self

    def _build_node(
        self, X: np.ndarray, durations: np.ndarray, events: np.ndarray, depth: int
    ) -> _SurvivalTreeNode:
        N, P = X.shape
        n_events = np.sum(events == 1)

        # Stopping criteria: pure node, min samples, max depth, or zero events
        if (
            (self.config.max_depth is not None and depth >= self.config.max_depth)
            or N < self.config.min_samples_split
            or n_events == 0
        ):
            return self._make_leaf(durations, events, depth)

        # Select candidate features
        if isinstance(self.config.max_features, str):
            if self.config.max_features == "sqrt":
                m_feat = max(1, int(round(math.sqrt(P))))
            elif self.config.max_features == "log2":
                m_feat = max(1, int(round(math.log2(P))))
            else:
                m_feat = P
        elif isinstance(self.config.max_features, int):
            m_feat = min(P, max(1, self.config.max_features))
        else:
            m_feat = P

        feat_indices = self.rng.choice(P, size=m_feat, replace=False)

        best_score = -1.0
        best_feat = None
        best_thresh = None

        for f_idx in feat_indices:
            x_col = X[:, f_idx]
            unique_vals = np.unique(x_col)
            if len(unique_vals) <= 1:
                continue

            # Candidate split thresholds (percentiles)
            if len(unique_vals) > 10:
                thresholds = np.percentile(unique_vals, np.linspace(10, 90, 9))
            else:
                thresholds = (unique_vals[:-1] + unique_vals[1:]) / 2.0

            for thresh in thresholds:
                left_mask = x_col <= thresh
                right_mask = ~left_mask

                n_left = np.sum(left_mask)
                n_right = np.sum(right_mask)

                if n_left < self.config.min_samples_leaf or n_right < self.config.min_samples_leaf:
                    continue

                score = self._compute_log_rank_score(durations, events, left_mask, right_mask)
                if score > best_score:
                    best_score = score
                    best_feat = f_idx
                    best_thresh = thresh

        if best_feat is None or best_score <= 0.0:
            return self._make_leaf(durations, events, depth)

        # Recurse
        left_mask = X[:, best_feat] <= best_thresh
        right_mask = ~left_mask

        left_child = self._build_node(X[left_mask], durations[left_mask], events[left_mask], depth + 1)
        right_child = self._build_node(X[right_mask], durations[right_mask], events[right_mask], depth + 1)

        return _SurvivalTreeNode(
            depth=depth,
            is_leaf=False,
            feature_idx=best_feat,
            threshold=best_thresh,
            left=left_child,
            right=right_child,
        )

    def _compute_log_rank_score(
        self, durations: np.ndarray, events: np.ndarray, left_mask: np.ndarray, right_mask: np.ndarray
    ) -> float:
        """Compute two-sample log-rank test statistic between left and right groups."""
        unique_event_times = np.unique(durations[events == 1])
        if len(unique_event_times) == 0:
            return 0.0

        numerator = 0.0
        denominator = 0.0

        for t in unique_event_times:
            # Group 1 (left)
            at_risk_1 = np.sum(left_mask & (durations >= t))
            events_1 = np.sum(left_mask & (durations == t) & (events == 1))

            # Group 2 (right)
            at_risk_2 = np.sum(right_mask & (durations >= t))
            events_2 = np.sum(right_mask & (durations == t) & (events == 1))

            at_risk_total = at_risk_1 + at_risk_2
            events_total = events_1 + events_2

            if at_risk_total <= 1 or events_total == 0:
                continue

            expected_1 = at_risk_1 * (events_total / at_risk_total)
            numerator += (events_1 - expected_1)

            var = (
                at_risk_1
                * at_risk_2
                * events_total
                * (at_risk_total - events_total)
                / ((at_risk_total**2) * (at_risk_total - 1))
            )
            denominator += var

        if denominator <= 1e-12:
            return 0.0

        z = abs(numerator) / math.sqrt(denominator)
        return float(z)

    def _make_leaf(self, durations: np.ndarray, events: np.ndarray, depth: int) -> _SurvivalTreeNode:
        """Build terminal leaf node with Kaplan-Meier and Nelson-Aalen estimators."""
        event_indices = np.where(events == 1)[0]
        unique_times = np.sort(np.unique(durations[event_indices])) if len(event_indices) > 0 else np.array([])

        km_survival = []
        na_cum_hazard = []
        cur_surv = 1.0
        cur_hazard = 0.0

        for t in unique_times:
            n_at_risk = np.sum(durations >= t)
            n_events = np.sum((durations == t) & (events == 1))
            if n_at_risk > 0:
                cur_surv *= (1.0 - n_events / n_at_risk)
                cur_hazard += (n_events / n_at_risk)
            km_survival.append(cur_surv)
            na_cum_hazard.append(cur_hazard)

        return _SurvivalTreeNode(
            depth=depth,
            is_leaf=True,
            event_times=unique_times,
            leaf_survival=np.array(km_survival, dtype=np.float64),
            leaf_cum_hazard=np.array(na_cum_hazard, dtype=np.float64),
        )

    def predict_survival_at(self, x: np.ndarray, t: float) -> float:
        """Route single patient down tree to terminal leaf and evaluate survival at horizon t."""
        node = self.root
        while not node.is_leaf:
            if x[node.feature_idx] <= node.threshold:
                node = node.left
            else:
                node = node.right
        return node.predict_survival_at(t)


class RandomSurvivalForestModel:
    """Random Survival Forest ensemble candidate for non-linear CKD progression modeling."""

    def __init__(self, config: Optional[RSFConfig] = None):
        self.config = config or RSFConfig()
        self.trees: List[_SurvivalTree] = []
        self.oob_indices_: List[np.ndarray] = []
        self.feature_names_: List[str] = []
        self.is_fitted_: bool = False

    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        durations: Union[np.ndarray, pd.Series, List[float]],
        events: Union[np.ndarray, pd.Series, List[int]],
        feature_names: Optional[List[str]] = None,
    ) -> "RandomSurvivalForestModel":
        """Fit the ensemble of survival trees via bootstrap aggregation."""
        if isinstance(X, pd.DataFrame):
            f_names = list(X.columns)
            X_arr = X.to_numpy(dtype=np.float64)
        else:
            X_arr = np.asarray(X, dtype=np.float64)
            f_names = feature_names if feature_names else [f"x_{i}" for i in range(X_arr.shape[1])]

        t_arr = np.asarray(durations, dtype=np.float64)
        e_arr = np.asarray(events, dtype=np.int32)
        N, P = X_arr.shape

        if len(t_arr) != N or len(e_arr) != N:
            raise ValueError(f"Dimension mismatch between X ({N}), durations ({len(t_arr)}), and events.")

        if np.any(np.isnan(X_arr)) or np.any(t_arr <= 0.0):
            raise ValueError("Invalid values in X or non-positive durations.")

        master_rng = np.random.default_rng(self.config.random_state)
        tree_seeds = master_rng.integers(0, 1000000, size=self.config.n_estimators)

        self.trees = []
        self.oob_indices_ = []
        self.feature_names_ = f_names

        for seed in tree_seeds:
            tree_rng = np.random.default_rng(seed)
            # Bootstrap sampling with replacement
            sample_idx = tree_rng.choice(N, size=N, replace=True)
            oob_idx = np.setdiff1d(np.arange(N), sample_idx)

            tree = _SurvivalTree(self.config, seed=int(seed))
            tree.fit(X_arr[sample_idx], t_arr[sample_idx], e_arr[sample_idx])

            self.trees.append(tree)
            self.oob_indices_.append(oob_idx)

        self.is_fitted_ = True
        return self

    def predict_survival(
        self, X: Union[np.ndarray, pd.DataFrame], time_horizon: float
    ) -> np.ndarray:
        """Predict ensemble event-free survival probability at time_horizon."""
        if not self.is_fitted_:
            raise ValueError("RSF model is not fitted.")

        X_arr = X.to_numpy(dtype=np.float64) if isinstance(X, pd.DataFrame) else np.asarray(X, dtype=np.float64)
        N = X_arr.shape[0]

        predictions = np.zeros(N, dtype=np.float64)
        for i in range(N):
            x = X_arr[i]
            tree_preds = [t.predict_survival_at(x, time_horizon) for t in self.trees]
            predictions[i] = np.mean(tree_preds)

        return np.clip(predictions, 0.0, 1.0)

    @property
    def model_type(self) -> str:
        """Explicit classification of the statistical estimand modelled by RSF."""
        return "cause_specific_survival"

    def predict_risk(
        self, X: Union[np.ndarray, pd.DataFrame], time_horizon: float
    ) -> np.ndarray:
        """Predict cumulative probability of kidney failure by time_horizon (1.0 - S(t)).

        WARNING ON COMPETING RISKS:
        This model is a cause-specific survival estimator where competing events (e.g. death)
        are treated as right-censoring. It does NOT provide subdistribution cumulative incidence (CIF)
        under competing risks.
        """
        return 1.0 - self.predict_survival(X, time_horizon)

    def compute_feature_importance(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        durations: Union[np.ndarray, List[float]],
        events: Union[np.ndarray, List[int]],
        time_horizon: float = 2.0,
    ) -> Dict[str, float]:
        """Compute strict Out-of-Bag (OOB) permutation importance across trees.

        Methodology (Breiman 2001, Ishwaran 2008):
        - For each survival tree b in the ensemble, evaluate ONLY the out-of-bag samples (OOB_b).
        - In-bag training observations NEVER contribute to the evaluation.
        - Permutes feature j within the OOB_b partition and computes increase in prediction error.
        - Averages error increase over trees with valid out-of-bag samples.

        Important Notice:
        - Reflects association/predictive importance, NOT causal influence.
        - Highly correlated features may share or split importance.
        """
        if not self.is_fitted_:
            raise ValueError("RSF model is not fitted.")

        X_arr = X.to_numpy(dtype=np.float64) if isinstance(X, pd.DataFrame) else np.asarray(X, dtype=np.float64)
        t_arr = np.asarray(durations, dtype=np.float64)
        e_arr = np.asarray(events, dtype=np.int32)
        P = X_arr.shape[1]
        n_trees = len(self.trees)

        rng = np.random.default_rng(self.config.random_state + 100)
        vimp_accum = np.zeros(P, dtype=np.float64)
        valid_tree_counts = np.zeros(P, dtype=np.float64)

        for b in range(n_trees):
            oob_idx = self.oob_indices_[b]
            if len(oob_idx) < 2:
                continue

            X_oob = X_arr[oob_idx]
            t_oob = t_arr[oob_idx]
            e_oob = e_arr[oob_idx]

            # Ground truth status at horizon for OOB samples
            y_oob = ((t_oob <= time_horizon) & (e_oob == 1)).astype(float)

            # Baseline unpermuted prediction for tree b on OOB_b
            tree = self.trees[b]
            base_surv = np.array([tree.predict_survival_at(X_oob[i], time_horizon) for i in range(len(oob_idx))])
            base_risk = 1.0 - base_surv
            base_err = np.mean((base_risk - y_oob) ** 2)

            for j in range(P):
                X_oob_perm = X_oob.copy()
                X_oob_perm[:, j] = rng.permutation(X_oob_perm[:, j])

                perm_surv = np.array([tree.predict_survival_at(X_oob_perm[i], time_horizon) for i in range(len(oob_idx))])
                perm_risk = 1.0 - perm_surv
                perm_err = np.mean((perm_risk - y_oob) ** 2)

                diff = perm_err - base_err
                vimp_accum[j] += diff
                valid_tree_counts[j] += 1.0

        vimp: Dict[str, float] = {}
        for j in range(P):
            count = max(1.0, valid_tree_counts[j])
            avg_importance = max(0.0, float(vimp_accum[j] / count))
            vimp[self.feature_names_[j]] = round(avg_importance, 6)

        return vimp
