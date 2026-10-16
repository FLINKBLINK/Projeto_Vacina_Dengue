from src.database.carga import recriar_banco
from src.database.conexao import listar_tabelas
from src.database.consultas_db import (
    consultar_casos,
    consultar_populacao,
    consultar_vacinacao_categoria,
    consultar_vacinacao_mensal,
)


def test_sqlite_importa_as_fontes_e_permite_consultas(tmp_path):
    caminho = tmp_path / "dengue_test.db"
    contagens = recriar_banco(caminho)

    assert set(listar_tabelas(caminho)) == {
        "metadados_carga",
        "populacao_municipio",
        "registros_sinan",
        "vacinacao_mensal",
        "vacinacao_sexo",
        "vacinacao_faixa_etaria",
    }
    assert contagens["populacao_municipio"] == 10
    assert contagens["registros_sinan"] > 100_000
    assert contagens["vacinacao_mensal"] > 100
    assert not consultar_populacao(caminho).empty
    assert not consultar_casos(caminho).empty
    assert not consultar_vacinacao_mensal(caminho).empty
    assert not consultar_vacinacao_categoria("sexo", caminho).empty
    assert not consultar_vacinacao_categoria("faixaetaria", caminho).empty


def test_categoria_invalida_e_rejeitada(tmp_path):
    caminho = tmp_path / "dengue_test.db"
    recriar_banco(caminho)
    try:
        consultar_vacinacao_categoria("idade", caminho)
    except ValueError as exc:
        assert "categoria" in str(exc)
    else:
        raise AssertionError("A consulta deveria rejeitar uma categoria inválida")
