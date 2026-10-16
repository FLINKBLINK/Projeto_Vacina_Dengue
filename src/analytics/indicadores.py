"""Indicadores calculados com validação de denominadores e dados ausentes."""
from __future__ import annotations
import numpy as np
import pandas as pd

def dividir_com_segurança(numerador, denominador):
    """Divide sem gerar infinito; denominadores nulos/zero retornam NaN."""
    n, d = np.asarray(numerador, dtype=float), np.asarray(denominador, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        resultado = np.where(np.isfinite(d) & (d != 0), n / d, np.nan)
    if resultado.ndim == 0:
        return float(resultado)
    return resultado

def calcular_doses_por_100_habitantes(doses, populacao):
    """Doses registradas por 100 habitantes; não equivale à cobertura vacinal oficial."""
    return dividir_com_segurança(doses, populacao) * 100

def calcular_variacao_percentual(valor_inicial, valor_final):
    """Variação percentual; retorna NaN se o valor inicial for zero/ausente."""
    return dividir_com_segurança(np.asarray(valor_final, dtype=float) - np.asarray(valor_inicial, dtype=float), valor_inicial) * 100

def calcular_resumo(series: pd.Series) -> dict:
    """Resumo descritivo ignorando ausentes, sem converter ausentes em zero."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {"n": 0, "media": np.nan, "mediana": np.nan, "minimo": np.nan, "maximo": np.nan}
    return {"n": int(s.count()), "media": float(s.mean()), "mediana": float(s.median()),
            "minimo": float(s.min()), "maximo": float(s.max())}
