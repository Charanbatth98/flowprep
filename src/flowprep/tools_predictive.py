"""Predictive tools - numpy-first, so the core install stays light.

Linear regression (OLS), logistic regression (gradient descent) and
k-means are implemented directly. If scikit-learn is installed, the
``random_forest`` tool uses it; otherwise it raises a clear install hint.
Every modelling tool writes predictions back as columns AND records its
metrics on ``ctx.info[node_id]`` so the UI can show R2 / RMSE / accuracy.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _xy(df, cfg):
    feats = cfg["features"]
    if isinstance(feats, str):
        feats = [f.strip() for f in feats.split(",")]
    X = df[feats].astype(float).to_numpy()
    return feats, X


def train_test_split(df, cfg, ctx):
    out = df.copy()
    rng = np.random.default_rng(int(cfg.get("seed", 42)))
    mask = rng.random(len(out)) < float(cfg.get("train_fraction", 0.8))
    out[cfg.get("new_column", "dataset")] = np.where(mask, "train", "test")
    return out


def linear_regression(df, cfg, ctx):
    feats, X = _xy(df, cfg)
    y = df[cfg["target"]].astype(float).to_numpy()
    Xb = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(Xb, y, rcond=None)
    pred = Xb @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    ctx.info[ctx.node_id] = {
        "model": "linear_regression", "intercept": round(float(coef[0]), 6),
        "coefficients": {f: round(float(c), 6) for f, c in zip(feats, coef[1:])},
        "r2": round(1 - ss_res / ss_tot, 6), "rmse": round(float(np.sqrt(ss_res / len(y))), 6)}
    out = df.copy()
    out[cfg.get("prediction_column", "prediction")] = np.round(pred, 6)
    return out


def logistic_regression(df, cfg, ctx):
    feats, X = _xy(df, cfg)
    y = df[cfg["target"]].astype(float).to_numpy()
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    w, b, lr = np.zeros(X.shape[1]), 0.0, float(cfg.get("learning_rate", 0.1))
    for _ in range(int(cfg.get("iterations", 500))):
        p = 1 / (1 + np.exp(-(Xs @ w + b)))
        w -= lr * (Xs.T @ (p - y)) / len(y)
        b -= lr * float(np.mean(p - y))
    prob = 1 / (1 + np.exp(-(Xs @ w + b)))
    pred = (prob >= 0.5).astype(int)
    ctx.info[ctx.node_id] = {"model": "logistic_regression",
                             "accuracy": round(float(np.mean(pred == y)), 6),
                             "coefficients": {f: round(float(c), 6) for f, c in zip(feats, w)},
                             "intercept": round(float(b), 6)}
    out = df.copy()
    out[cfg.get("probability_column", "probability")] = np.round(prob, 6)
    out[cfg.get("prediction_column", "prediction")] = pred
    return out


def kmeans(df, cfg, ctx):
    feats, X = _xy(df, cfg)
    k = int(cfg.get("k", 3))
    rng = np.random.default_rng(int(cfg.get("seed", 42)))
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    cent = Xs[rng.choice(len(Xs), size=min(k, len(Xs)), replace=False)]
    for _ in range(100):
        labels = np.argmin(((Xs[:, None, :] - cent[None]) ** 2).sum(-1), axis=1)
        new = np.array([Xs[labels == j].mean(0) if (labels == j).any() else cent[j] for j in range(len(cent))])
        if np.allclose(new, cent):
            break
        cent = new
    ctx.info[ctx.node_id] = {"model": "kmeans", "k": k, "cluster_sizes": np.bincount(labels).tolist()}
    out = df.copy()
    out[cfg.get("new_column", "cluster")] = labels
    return out


def random_forest(df, cfg, ctx):
    try:
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    except ImportError as e:
        raise RuntimeError("random_forest needs scikit-learn: pip install 'flowprep[ml]'") from e
    feats, X = _xy(df, cfg)
    y = df[cfg["target"]]
    is_class = y.dtype == object or y.nunique() <= 20 and cfg.get("task", "auto") != "regression"
    model = (RandomForestClassifier if is_class else RandomForestRegressor)(
        n_estimators=int(cfg.get("n_estimators", 200)), random_state=int(cfg.get("seed", 42)))
    model.fit(X, y)
    out = df.copy()
    out[cfg.get("prediction_column", "prediction")] = model.predict(X)
    score = float(model.score(X, y))
    ctx.info[ctx.node_id] = {"model": "random_forest", "task": "classification" if is_class else "regression",
                             "score_on_input": round(score, 6),
                             "feature_importance": {f: round(float(v), 6) for f, v in zip(feats, model.feature_importances_)}}
    return out


def correlation(df, cfg, ctx):
    cols = cfg.get("columns") or list(df.select_dtypes("number").columns)
    corr = df[cols].corr().reset_index().rename(columns={"index": "column"})
    return corr


def evaluate(df, cfg, ctx):
    actual, pred = df[cfg["actual"]].astype(float), df[cfg["prediction"]].astype(float)
    rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
    mae = float(np.mean(np.abs(actual - pred)))
    ss_res, ss_tot = float(np.sum((actual - pred) ** 2)), float(np.sum((actual - actual.mean()) ** 2)) or 1.0
    return pd.DataFrame([{"rmse": round(rmse, 6), "mae": round(mae, 6), "r2": round(1 - ss_res / ss_tot, 6), "rows": len(df)}])


TOOLS = {
    "train_test_split": dict(fn=lambda i, c, x: train_test_split(i[0], c, x), inputs=1, category="Predictive", label="Train / Test Split",
                             fields={"train_fraction": "number", "seed": "number", "new_column": "text"}),
    "linear_regression": dict(fn=lambda i, c, x: linear_regression(i[0], c, x), inputs=1, category="Predictive", label="Linear Regression",
                              fields={"features": "list", "target": "text", "prediction_column": "text"}),
    "logistic_regression": dict(fn=lambda i, c, x: logistic_regression(i[0], c, x), inputs=1, category="Predictive", label="Logistic Regression",
                                fields={"features": "list", "target": "text", "prediction_column": "text", "probability_column": "text"}),
    "kmeans": dict(fn=lambda i, c, x: kmeans(i[0], c, x), inputs=1, category="Predictive", label="K-Means Clustering",
                   fields={"features": "list", "k": "number", "seed": "number", "new_column": "text"}),
    "random_forest": dict(fn=lambda i, c, x: random_forest(i[0], c, x), inputs=1, category="Predictive", label="Random Forest (needs scikit-learn)",
                          fields={"features": "list", "target": "text", "n_estimators": "number", "prediction_column": "text"}),
    "correlation": dict(fn=lambda i, c, x: correlation(i[0], c, x), inputs=1, category="Predictive", label="Correlation",
                        fields={"columns": "list"}),
    "evaluate": dict(fn=lambda i, c, x: evaluate(i[0], c, x), inputs=1, category="Predictive", label="Evaluate (RMSE / MAE / R2)",
                     fields={"actual": "text", "prediction": "text"}),
}
