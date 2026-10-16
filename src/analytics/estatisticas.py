"""Testes estatísticos com validação explícita da amostra."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

def correlacao_pearson(x, y) -> dict:
    """Calcula Pearson usando apenas pares completos e informa n efetivo."""
    pares = pd.DataFrame({"x": pd.to_numeric(pd.Series(x), errors="coerce"),
                          "y": pd.to_numeric(pd.Series(y), errors="coerce")}).dropna()
    pares = pares[np.isfinite(pares["x"]) & np.isfinite(pares["y"])]
    n = len(pares)
    resultado = {"r": np.nan, "p_value": np.nan, "n": n, "interpretacao": "Amostra insuficiente."}
    if n < 3:
        return resultado
    if pares["x"].nunique() < 2 or pares["y"].nunique() < 2:
        resultado["interpretacao"] = "Correlação indefinida: uma variável não varia."
        return resultado
    r, p = pearsonr(pares["x"], pares["y"])
    resultado.update({"r": float(r), "p_value": float(p)})
    resultado["interpretacao"] = ("Associação linear estatisticamente significativa (α = 0,05); isso não demonstra causalidade."
                                  if p < 0.05 else
                                  "Não foi identificada associação linear estatisticamente significativa (α = 0,05).")
    return resultado
