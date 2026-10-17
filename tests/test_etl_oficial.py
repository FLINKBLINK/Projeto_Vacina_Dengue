import sqlite3

import pytest

from src.ingestion.etl_oficial import (
    ErroETLOficial,
    _lista_registros,
    carregar_registros,
    inicializar_tabelas_oficiais,
    iterar_paginas,
)


def test_lista_registros_aceita_lista_raiz_e_chaves_comuns():
    assert _lista_registros([{"a": 1}]) == [{"a": 1}]
    assert _lista_registros({"data": [{"b": 2}]}) == [{"b": 2}]


def test_lista_registros_rejeita_resposta_ambigua():
    with pytest.raises(ErroETLOficial):
        _lista_registros({"metadata": {"total": 2}})


def test_iterar_paginas_usa_offset_e_para_na_pagina_curta(monkeypatch):
    chamadas = []

    def fake(path, params=None, **kwargs):
        chamadas.append(params.copy())
        pagina = params["offset"]
        inicio = pagina * 2
        return [{"id": i} for i in range(inicio, min(inicio + 2, 5))]

    monkeypatch.setattr("src.ingestion.etl_oficial.consultar_pagina", fake)
    paginas = list(iterar_paginas("/endpoint", {"ano": 2025}, page_size=2))
    assert [len(p) for p in paginas] == [2, 2, 1]
    assert [c["offset"] for c in chamadas] == [0, 1, 2]


def test_carga_idempotente_filtra_municipios_fora_da_regiao():
    conn = sqlite3.connect(":memory:")
    inicializar_tabelas_oficiais(conn)
    registros = [
        {"cod_mun": 3543402, "dt_notific": "2025-01-01", "nu_notific": "x1"},
        {"cod_mun": 9999999, "dt_notific": "2025-01-01", "nu_notific": "x2"},
    ]
    primeira = carregar_registros(conn, "sinan_dengue", registros, ano_referencia=2025)
    segunda = carregar_registros(conn, "sinan_dengue", registros, ano_referencia=2025)
    assert primeira == {"recebidos": 2, "regiao": 1}
    assert segunda == primeira
    assert conn.execute("SELECT COUNT(*) FROM oficiais_registros").fetchone()[0] == 1


def test_tabela_legada_nao_e_substituida():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE registros_sinan (id INTEGER PRIMARY KEY, municipio TEXT)")
    inicializar_tabelas_oficiais(conn)
    tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "registros_sinan" in tabelas
    assert "oficiais_registros" in tabelas
