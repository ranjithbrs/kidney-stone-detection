"""Modular Cox Proportional Hazards survival model for Engine 3.

Provides an interpretable, mathematically rigorous cause-specific Cox Proportional
Hazards implementation using SciPy optimization with Breslow baseline hazard estimation.

Clinical & Scientific Guardrails:
- Hazard Ratios (HR) express instantaneous relative rate ratios; they are NOT direct
  cumulative probabilities of kidney failure.
- Standard cause-specific Cox PH treats competing events (death before kidney failure)
  as right-censoring, which may overestimate cumulative incidence in high-competing-risk cohorts.
- Preprocessing and feature parameters are fitted strictly on training data.
- Feature variance and collinearity diagnostics are performed prior to optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm


class SurvivalModelError(ValueError):
    """Raised when survival model inputs violate assumptions or optimization fails."""

    pass


@dataclass
class CoxPHConfig:
    """Reproducible configuration for Cox Proportional Hazards model fitting.

    Attributes:
        l2_penalty: Ridge regularization parameter lambda >= 0.0 to stabilize optimization
            in the presence of high multicollinearity or small sample sizes.
        max_iter: Maximum BFGS optimization iterations.
        tolerance: Convergence tolerance for gradient norm.
        random_state: Explicit random seed for reproducibility.
    """

    l2_penalty: float = 0.0
    max_iter: int = 300
    tolerance: float = 1e-7
    random_state: int = 42


@dataclass
class CoxCoefficientResult:
    """Detailed estimation results for an individual predictor in the Cox PH model."""

    feature_name: str
    coef: float
    hazard_ratio: float
    std_err: float
    z_score: float
    p_value: float
    ci_lower_95: float
    ci_upper_95: float
    hr_ci_lower_95: float
    hr_ci_upper_95: float


class CoxProportionalHazardsModel:
    """Interpretable cause-specific Cox Proportional Hazards model for CKD progression.

    Estimates proportional hazards hazard ratios and Breslow baseline cumulative hazards,
    enabling time-dependent risk estimation at specified horizons (e.g. 2-year and 5-year).
    """

    def __init__(self, config: Optional[CoxPHConfig] = None):
        self.config = config or CoxPHConfig()
        self.feature_names_: List[str] = []
        self.coefficients_: Optional[np.ndarray] = None
        self.covariance_matrix_: Optional[np.ndarray] = None
        self.standard_errors_: Optional[np.ndarray] = None
        self.is_fitted_: bool = False

        # Breslow baseline hazard attributes
        self.baseline_event_times_: Optional[np.ndarray] = None
        self.baseline_cum_hazard_: Optional[np.ndarray] = None
        self.baseline_survival_: Optional[np.ndarray] = None

    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        durations: Union[np.ndarray, pd.Series, List[float]],
        events: Union[np.ndarray, pd.Series, List[int]],
        feature_names: Optional[List[str]] = None,
    ) -> "CoxProportionalHazardsModel":
        """Fit the Cox PH model via maximum partial likelihood.

        Args:
            X: 2D feature matrix of shape (N, P).
            durations: Follow-up durations in years (all > 0).
            events: Binary event indicators (1 = Kidney Failure, 0 = Censored/Competing Event).
            feature_names: Optional feature names if X is a raw numpy array.

        Returns:
            self: The fitted model instance.
        """
        # 1. Parse and validate inputs
        X_arr, f_names = self._prepare_features(X, feature_names)
        t_arr = np.asarray(durations, dtype=np.float64)
        e_arr = np.asarray(events, dtype=np.int32)

        N, P = X_arr.shape
        if len(t_arr) != N or len(e_arr) != N:
            raise SurvivalModelError(
                f"Dimension mismatch: X has {N} samples, durations has {len(t_arr)}, events has {len(e_arr)}."
            )

        if np.any(t_arr <= 0.0):
            raise SurvivalModelError("All follow-up durations must be strictly positive (> 0.0).")

        if np.sum(e_arr == 1) < 1:
            raise SurvivalModelError("At least one primary event (events == 1) is required to fit Cox PH.")

        # 2. Defensive checks: Collinearity and Constant Features
        variances = np.var(X_arr, axis=0)
        for idx, var in enumerate(variances):
            if var < 1e-9:
                raise SurvivalModelError(
                    f"Constant or near-constant predictor detected: '{f_names[idx]}' has variance {var:.2e}. "
                    "Cannot fit Cox PH with invariant features."
                )

        if P > 1:
            corr_mat = np.corrcoef(X_arr, rowvar=False)
            if np.any(np.isnan(corr_mat)):
                raise SurvivalModelError("Correlation matrix contains NaN values; check for invariant features.")
            upper_tri = np.triu(corr_mat, k=1)
            high_collinear = np.where(np.abs(upper_tri) > 0.999)
            if len(high_collinear[0]) > 0:
                i, j = high_collinear[0][0], high_collinear[1][0]
                raise SurvivalModelError(
                    f"Near-perfect collinearity detected between '{f_names[i]}' and '{f_names[j]}' "
                    f"(correlation = {corr_mat[i, j]:.4f}). Remove redundant feature before fitting."
                )

        # 3. Sort by follow-up time ascending for efficient risk-set summation
        order = np.argsort(t_arr)
        X_sorted = X_arr[order]
        t_sorted = t_arr[order]
        e_sorted = e_arr[order]

        # Precompute distinct event times and tie groupings (Breslow tie handling)
        event_indices = np.where(e_sorted == 1)[0]
        unique_event_times = np.sort(np.unique(t_sorted[event_indices]))

        # Map each distinct event time tau_k to:
        # - risk_set_start_idx: first index where t_sorted >= tau_k
        # - event_idx: indices in sorted array where t_sorted == tau_k and e_sorted == 1
        tie_groups = []
        for tau_k in unique_event_times:
            r_start = int(np.searchsorted(t_sorted, tau_k, side="left"))
            ev_idx = np.where((t_sorted == tau_k) & (e_sorted == 1))[0]
            tie_groups.append((tau_k, r_start, ev_idx, len(ev_idx)))

        # 4. Breslow Partial Log-Likelihood & Gradient Formulation
        def neg_log_partial_likelihood_and_grad(beta: np.ndarray) -> Tuple[float, np.ndarray]:
            risk_scores = np.dot(X_sorted, beta)  # (N,)
            max_risk = np.max(risk_scores)
            exp_risk = np.exp(risk_scores - max_risk)

            # Cumulative sum from right: cumsum_exp_risk[i] = sum_{j >= i} exp(x_j^T beta - max_risk)
            cumsum_exp_risk = np.cumsum(exp_risk[::-1])[::-1]
            cumsum_exp_risk_X = np.cumsum((exp_risk[:, None] * X_sorted)[::-1], axis=0)[::-1]

            loss = 0.0
            grad = np.zeros(P, dtype=np.float64)

            # Breslow method: All d_k events at tau_k share the identical risk set R(tau_k)
            for tau_k, r_start, ev_idx, d_k in tie_groups:
                s0_k = cumsum_exp_risk[r_start]
                s1_k = cumsum_exp_risk_X[r_start]

                sum_lp_k = np.sum(risk_scores[ev_idx])
                sum_x_k = np.sum(X_sorted[ev_idx], axis=0)

                loss -= (sum_lp_k - d_k * (max_risk + np.log(s0_k)))
                grad -= (sum_x_k - d_k * (s1_k / s0_k))

            # L2 ridge penalty
            if self.config.l2_penalty > 0.0:
                loss += 0.5 * self.config.l2_penalty * np.sum(beta**2)
                grad += self.config.l2_penalty * beta

            return loss, grad

        # 5. Optimize via SciPy BFGS
        initial_beta = np.zeros(P, dtype=np.float64)
        opt_res = minimize(
            fun=neg_log_partial_likelihood_and_grad,
            x0=initial_beta,
            method="BFGS",
            jac=True,
            options={"maxiter": self.config.max_iter, "gtol": self.config.tolerance},
        )

        if not opt_res.success:
            # Fallback to L-BFGS-B
            opt_res = minimize(
                fun=neg_log_partial_likelihood_and_grad,
                x0=initial_beta,
                method="L-BFGS-B",
                jac=True,
                options={"maxiter": self.config.max_iter, "ftol": self.config.tolerance},
            )

        # Strict convergence verification: Never return false inferential statistics
        if not opt_res.success:
            # Check if gradient is sufficiently close to zero despite message
            _, final_grad = neg_log_partial_likelihood_and_grad(opt_res.x)
            grad_norm = np.linalg.norm(final_grad)
            if grad_norm > 1e-3:
                raise SurvivalModelError(
                    f"Cox PH optimization failed to converge ({opt_res.message}, grad_norm={grad_norm:.2e}). "
                    "Cannot compute valid model parameters or standard errors."
                )

        fitted_beta = opt_res.x

        # Compute Analytical Observed Information Matrix (Hessian of log-partial likelihood)
        risk_scores = np.dot(X_sorted, fitted_beta)
        max_risk = np.max(risk_scores)
        exp_risk = np.exp(risk_scores - max_risk)
        cumsum_exp_risk = np.cumsum(exp_risk[::-1])[::-1]
        cumsum_exp_risk_X = np.cumsum((exp_risk[:, None] * X_sorted)[::-1], axis=0)[::-1]

        # S2 second-moment tensor: S2[i] = sum_{j >= i} x_j x_j^T exp(x_j^T beta)
        X_outer = np.einsum("ni,nj->nij", X_sorted, X_sorted)
        cumsum_exp_risk_X2 = np.cumsum((exp_risk[:, None, None] * X_outer)[::-1], axis=0)[::-1]

        obs_info = np.zeros((P, P), dtype=np.float64)
        for tau_k, r_start, ev_idx, d_k in tie_groups:
            s0_k = cumsum_exp_risk[r_start]
            s1_k = cumsum_exp_risk_X[r_start]
            s2_k = cumsum_exp_risk_X2[r_start]

            x_bar = s1_k / s0_k
            v_k = (s2_k / s0_k) - np.outer(x_bar, x_bar)
            obs_info += d_k * v_k

        if self.config.l2_penalty > 0.0:
            obs_info += self.config.l2_penalty * np.eye(P)

        # Check conditioning of observed information matrix
        rcond = np.linalg.cond(obs_info)
        if rcond > 1e12 or np.isnan(rcond):
            raise SurvivalModelError(
                f"Observed information matrix is singular/ill-conditioned (condition number = {rcond:.2e}). "
                "Standard errors cannot be reliably computed."
            )

        try:
            cov_mat = np.linalg.inv(obs_info)
        except np.linalg.LinAlgError:
            raise SurvivalModelError("Could not invert observed information matrix for standard errors.")

        diag_cov = np.diag(cov_mat)
        if np.any(diag_cov < 0.0):
            raise SurvivalModelError("Negative variance encountered on diagonal of covariance matrix.")

        std_errs = np.sqrt(diag_cov)

        self.feature_names_ = f_names
        self.coefficients_ = fitted_beta
        self.covariance_matrix_ = cov_mat
        self.standard_errors_ = std_errs

        # 6. Estimate Breslow Baseline Cumulative Hazard
        self._compute_breslow_baseline(X_sorted, t_sorted, e_sorted, fitted_beta)
        self.is_fitted_ = True
        return self

    def _compute_breslow_baseline(
        self, X_sorted: np.ndarray, t_sorted: np.ndarray, e_sorted: np.ndarray, beta: np.ndarray
    ) -> None:
        """Compute non-parametric Breslow baseline cumulative hazard H_0(t)."""
        risk_scores = np.dot(X_sorted, beta)
        exp_risk = np.exp(risk_scores)

        # Unique event times
        event_indices = np.where(e_sorted == 1)[0]
        unique_event_times = np.unique(t_sorted[event_indices])

        baseline_hazard_increments = []
        for t_k in unique_event_times:
            # Events at t_k
            d_k = np.sum((t_sorted == t_k) & (e_sorted == 1))
            # Risk set: all subjects with follow-up >= t_k
            risk_set_sum = np.sum(exp_risk[t_sorted >= t_k])
            baseline_hazard_increments.append(d_k / risk_set_sum if risk_set_sum > 0 else 0.0)

        cum_hazard = np.cumsum(baseline_hazard_increments)
        self.baseline_event_times_ = unique_event_times
        self.baseline_cum_hazard_ = cum_hazard
        self.baseline_survival_ = np.exp(-cum_hazard)

    def _prepare_features(
        self, X: Union[np.ndarray, pd.DataFrame], feature_names: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[str]]:
        """Normalize feature container to numpy array and string feature names."""
        if isinstance(X, pd.DataFrame):
            f_names = list(X.columns)
            X_arr = X.to_numpy(dtype=np.float64)
        elif isinstance(X, np.ndarray):
            X_arr = np.asarray(X, dtype=np.float64)
            if feature_names is not None:
                if len(feature_names) != X_arr.shape[1]:
                    raise SurvivalModelError("Length of feature_names does not match number of columns in X.")
                f_names = list(feature_names)
            else:
                f_names = [f"x_{i}" for i in range(X_arr.shape[1])]
        else:
            raise SurvivalModelError(f"Unsupported feature container type: {type(X)}.")

        if np.any(np.isnan(X_arr)) or np.any(np.isinf(X_arr)):
            raise SurvivalModelError("Feature matrix X contains NaN or infinite values; impute before fitting.")

        return X_arr, f_names

    def get_baseline_survival_at(self, time_horizon: float) -> float:
        """Evaluate baseline survival S_0(t) at time_horizon using step-function interpolation."""
        if not self.is_fitted_ or self.baseline_event_times_ is None:
            raise SurvivalModelError("Model is not fitted.")

        if len(self.baseline_event_times_) == 0 or time_horizon < self.baseline_event_times_[0]:
            return 1.0

        idx = np.searchsorted(self.baseline_event_times_, time_horizon, side="right") - 1
        return float(self.baseline_survival_[idx])

    def predict_risk(
        self, X: Union[np.ndarray, pd.DataFrame], time_horizon: float
    ) -> np.ndarray:
        """Predict cumulative probability of kidney failure by time_horizon (e.g. 2.0 or 5.0 years).

        Formula:
            Risk(t | x) = 1 - S_0(t)^exp(x^T beta)

        Strictly bounded in [0.0, 1.0].
        """
        if not self.is_fitted_:
            raise SurvivalModelError("Model is not fitted.")

        X_arr, _ = self._prepare_features(X, self.feature_names_)
        s0_t = self.get_baseline_survival_at(time_horizon)

        linear_predictors = np.dot(X_arr, self.coefficients_)
        # Numerical protection: clip LP to [-50, 50]
        clipped_lp = np.clip(linear_predictors, -50.0, 50.0)
        relative_hazards = np.exp(clipped_lp)

        # Survival S(t | x) = s0_t ^ exp(lp)
        survival_probs = np.power(s0_t, relative_hazards)
        risks = 1.0 - survival_probs
        return np.clip(risks, 0.0, 1.0)

    def predict_survival(
        self, X: Union[np.ndarray, pd.DataFrame], time_horizon: float
    ) -> np.ndarray:
        """Predict event-free survival probability S(t | x) at time_horizon."""
        return 1.0 - self.predict_risk(X, time_horizon)

    def summary_table(self) -> pd.DataFrame:
        """Produce tabular report of estimated coefficients, hazard ratios, and 95% CIs."""
        if not self.is_fitted_:
            raise SurvivalModelError("Model is not fitted.")

        rows = []
        for i, name in enumerate(self.feature_names_):
            c = float(self.coefficients_[i])
            se = float(self.standard_errors_[i])
            hr = math.exp(c)
            z = c / se if se > 0 else 0.0
            p = 2.0 * (1.0 - norm.cdf(abs(z)))
            ci_low = c - 1.96 * se
            ci_high = c + 1.96 * se
            hr_low = math.exp(ci_low)
            hr_high = math.exp(ci_high)

            rows.append(
                {
                    "feature": name,
                    "coef": round(c, 5),
                    "hazard_ratio": round(hr, 4),
                    "std_err": round(se, 5),
                    "z_score": round(z, 3),
                    "p_value": round(p, 5),
                    "ci_95_lower": round(ci_low, 5),
                    "ci_95_upper": round(ci_high, 5),
                    "hr_ci_95_lower": round(hr_low, 4),
                    "hr_ci_95_upper": round(hr_high, 4),
                }
            )
        return pd.DataFrame(rows)
