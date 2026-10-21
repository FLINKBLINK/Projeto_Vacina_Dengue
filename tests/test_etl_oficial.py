import sqlite3

import pytest

from src.ingestion.etl_oficial import (
    ErroETLOficial,
    _lista_registros,
    carregar_registros,
    executar_extracao,
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
        inicio = pagina
        return [{"id": i} for i in range(inicio, min(inicio + 2, 5))]

    monkeypatch.setattr("src.ingestion.etl_oficial.consultar_pagina", fake)
    paginas = list(iterar_paginas("/endpoint", {"ano": 2025}, page_size=2))
    assert [len(p) for p in paginas] == [2, 2, 1]
    assert [c["offset"] for c in chamadas] == [0, 2, 4]


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

def test_extracao_sinan_processa_arquivo_nacional_uma_vez_por_ano(tmp_path, monkeypatch):
    chamadas = []

    def fake_iterar(ano, *, page_size=1000, session=None, archive_path=None):
        chamadas.append(ano)
        yield [{
            "id_mn_resi": "354340",
            "dt_notific": f"{ano}-01-01",
            "nu_notific": "teste",
        }]

    monkeypatch.setattr("src.ingestion.etl_oficial.iterar_sinan_arquivo", fake_iterar)
    db = tmp_path / "etl_teste.db"
    resumo = executar_extracao(
        db,
        anos_sinan=(2024,),
        anos_populacao=(),
        page_size=1000,
        max_pages_por_consulta=1,
    )

    assert chamadas == [2024]
    assert len(resumo["fontes"]) == 1
    assert resumo["fontes"][0]["fonte"] == "sinan_dengue"
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM oficiais_registros WHERE fonte='sinan_dengue'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM oficiais_execucoes WHERE fonte='sinan_dengue' AND status='sucesso'"
        ).fetchone()[0] == 1



def test_mapeamento_ibge_dos_dez_municipios_do_projeto():
    from src.ingestion.etl_oficial import MUNICIPIOS_IBGE, _codigo_municipio

    esperados = {
        "3505601": "Barrinha",
        "3507805": "Brodowski",
        "3513108": "Cravinhos",
        "3518859": "Guatapará",
        "3524303": "Jardinópolis",
        "3540200": "Pontal",
        "3540903": "Pradópolis",
        "3543402": "Ribeirão Preto",
        "3551504": "Serrana",
        "3551702": "Sertãozinho",
    }
    assert MUNICIPIOS_IBGE == esperados

    for codigo, municipio in esperados.items():
        assert _codigo_municipio({"id_mn_resi": codigo}) == codigo
        assert _codigo_municipio({"id_mn_resi": codigo[:6]}) == codigo
        assert MUNICIPIOS_IBGE[codigo] == municipio


def test_codigo_de_municipio_fora_da_regiao_nao_e_mapeado():
    from src.ingestion.etl_oficial import _codigo_municipio

    # 3518800 é Guarulhos; não pode ser confundido com Guatapará (3518859).
    assert _codigo_municipio({"id_mn_resi": "3518800"}) is None
    assert _codigo_municipio({"id_mn_resi": "351880"}) is None
    assert _codigo_municipio({"id_mn_resi": "320530"}) is None
