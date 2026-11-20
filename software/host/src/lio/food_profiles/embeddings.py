"""Optional UMAP / t-SNE exploratory embeddings (lazy imports)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from lio.food_profiles.features import FeatureBatch
from lio.food_profiles.preprocessing import fit_preprocess, transform_preprocess
from lio.food_profiles.schema import finite_json

Method = Literal["umap", "tsne"]


@dataclass
class EmbeddingResult:
    method: str
    available: bool
    reason: str
    coords: np.ndarray | None
    row_ids: list[str]
    params: dict[str, Any]
    install_hint: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return finite_json(
            {
                "method": self.method,
                "available": self.available,
                "reason": self.reason,
                "coords": self.coords,
                "row_ids": self.row_ids,
                "params": self.params,
                "install_hint": self.install_hint,
                "note": "exploratory sensitivity view only; not a frozen food map",
            }
        )


def _complete_matrix(batch: FeatureBatch) -> tuple[np.ndarray, list[str]]:
    prepped = transform_preprocess(batch, fit_preprocess(batch))
    ok = np.isfinite(prepped.X).all(axis=1)
    return prepped.X[ok], [prepped.row_ids[i] for i in range(prepped.n_rows) if ok[i]]


def embed(
    batch: FeatureBatch,
    method: Method = "tsne",
    *,
    n_components: int = 2,
    random_state: int = 0,
    **kwargs: Any,
) -> EmbeddingResult:
    X, row_ids = _complete_matrix(batch)
    if X.shape[0] < 3:
        return EmbeddingResult(method, False, "need_at_least_3_complete_rows", None, row_ids, {})
    if method == "tsne":
        try:
            from sklearn.manifold import TSNE
        except ImportError:
            return EmbeddingResult(
                method,
                False,
                "missing_dependency",
                None,
                row_ids,
                {},
                install_hint="pip install 'lio[profiles]'",
            )
        perplexity = float(kwargs.get("perplexity", min(30, max(2, X.shape[0] - 1))))
        # sklearn >=1.2 uses max_iter; older uses n_iter - try max_iter first
        try:
            tsne = TSNE(
                n_components=n_components,
                random_state=random_state,
                perplexity=perplexity,
                init="pca",
                learning_rate="auto",
                max_iter=int(kwargs.get("max_iter", 500)),
            )
        except TypeError:
            tsne = TSNE(
                n_components=n_components,
                random_state=random_state,
                perplexity=perplexity,
                init="pca",
                learning_rate="auto",
                n_iter=int(kwargs.get("max_iter", 500)),
            )
        coords = tsne.fit_transform(X)
        return EmbeddingResult(
            method,
            True,
            "ok",
            coords.astype(np.float64),
            row_ids,
            {"perplexity": perplexity, "random_state": random_state},
        )
    if method == "umap":
        try:
            import umap
        except ImportError:
            return EmbeddingResult(
                method,
                False,
                "missing_dependency",
                None,
                row_ids,
                {},
                install_hint="pip install 'lio[embeddings]'",
            )
        n_neighbors = int(kwargs.get("n_neighbors", min(15, X.shape[0] - 1)))
        reducer = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            random_state=random_state,
            min_dist=float(kwargs.get("min_dist", 0.1)),
        )
        coords = reducer.fit_transform(X)
        return EmbeddingResult(
            method,
            True,
            "ok",
            np.asarray(coords, dtype=np.float64),
            row_ids,
            {"n_neighbors": n_neighbors, "random_state": random_state},
        )
    return EmbeddingResult(method, False, "unknown_method", None, row_ids, {})
