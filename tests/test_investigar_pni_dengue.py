from __future__ import annotations

from scripts.investigar_pni_dengue import analisar_registros, consultar_ano, extrair_registros


class RespostaFake:
    def __init__(self, dados):
        self.dados = dados

    def raise_for_status(self):
        return None

    def json(self):
        return self.dados


class SessaoFake:
    def __init__(self, paginas):
        self.paginas = list(paginas)
        self.chamadas = []

    def get(self, url, *, params, headers, timeout):
        self.chamadas.append({"url": url, "params": params})
        return RespostaFake(self.paginas[len(self.chamadas) - 1])


def registro(codigo="99", descricao="Vacina dengue", municipio_paciente="3543402"):
    return {
        "codigo_vacina": codigo,
        "descricao_vacina": descricao,
        "codigo_dose_vacina": "2",
        "data_vacina": "2024-04-15",
        "numero_idade_paciente": 12,
        "tipo_sexo_paciente": "F",
        "codigo_municipio_paciente": municipio_paciente,
        "codigo_municipio_estabelecimento": "3543402",
        "identificador_pessoal": "NAO_DEVE_APARECER_NO_RELATORIO",
    }


def test_extrair_registros_aceita_lista_e_envelope():
    amostra = [registro()]
    assert extrair_registros(amostra) == amostra
    assert extrair_registros({"data": amostra}) == amostra


def test_analisar_registros_identifica_descricao_dengue_sem_expor_registro():
    resultado = analisar_registros([registro(), registro(codigo="10", descricao="Influenza")])

    assert resultado["registros_analisados"] == 2
    assert resultado["possiveis_codigos_dengue"] == [
        {
            "codigo_vacina": "99",
            "descricao": "Vacina dengue",
            "registros": 1,
            "descricao_menciona_dengue": True,
        }
    ]
    assert resultado["campos_semanticos"]["idade"]["registros_preenchidos"] == 2
    assert "identificador_pessoal" not in resultado["campos_retornados"]
    assert "identificador_pessoal" not in str(resultado)


def test_consultar_ano_pagina_ate_encontrar_pagina_curta():
    sessao = SessaoFake([[registro(), registro()], [registro(codigo="10")]])

    resultado = consultar_ano(2024, page_size=2, max_pages=5, session=sessao)

    assert resultado["paginas_consultadas"] == 2
    assert resultado["registros_analisados"] == 3
    assert [chamada["params"]["offset"] for chamada in sessao.chamadas] == [0, 1]


def test_consultar_ano_respeita_limite_de_paginas():
    sessao = SessaoFake([[registro(), registro()], [registro(), registro()]])

    resultado = consultar_ano(2025, page_size=2, max_pages=2, session=sessao)

    assert resultado["paginas_consultadas"] == 2
    assert resultado["registros_analisados"] == 4


def test_validacao_de_parametros():
    sessao = SessaoFake([])

    try:
        consultar_ano(2024, page_size=1001, session=sessao)
    except ValueError as exc:
        assert "page_size" in str(exc)
    else:
        raise AssertionError("Esperava ValueError para page_size acima de 1000.")
