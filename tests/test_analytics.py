import numpy as np
import pandas as pd

from src.analytics.consultas import normalizar_municipio
from src.analytics.indicadores import calcular_doses_por_100_habitantes, calcular_variacao_percentual, dividir_com_segurança
from src.analytics.estatisticas import correlacao_pearson


def test_normalizar_municipio_remove_estado_e_acento():
    assert normalizar_municipio("Barrinha (SP)") == "Barrinha"
    assert normalizar_municipio("RIBEIRAO PRETO") == "Ribeirão Preto"
    assert normalizar_municipio("CRAVINHHOS") == "Cravinhos"


def test_doses_por_100_habitantes_nao_e_cobertura():
    assert calcular_doses_por_100_habitantes(25, 1000) == 2.5


def test_divisao_com_denominador_zero_retorna_nan():
    assert np.isnan(dividir_com_segurança(5, 0))


def test_variacao_percentual():
    assert calcular_variacao_percentual(100, 150) == 50
    assert np.isnan(calcular_variacao_percentual(0, 15))


def test_pearson_retorna_n_efetivo():
    resultado = correlacao_pearson(pd.Series([1, 2, 3, np.nan, 4]), pd.Series([2, 4, 6, 7, 8]))
    assert resultado["n"] == 4
    assert resultado["r"] > 0.99


def test_pearson_sem_variacao_fica_indefinido():
    resultado = correlacao_pearson([1, 1, 1], [2, 3, 4])
    assert np.isnan(resultado["r"])
    assert "indefinida" in resultado["interpretacao"]
