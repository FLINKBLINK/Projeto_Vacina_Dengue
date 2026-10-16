import scripts.diagnosticar_sinan_municipios as diagnostico


def test_codigo_municipal_normaliza_seis_ou_sete_digitos():
    assert diagnostico.codigo_municipal({"id_mn_resi": "354340"}, "id_mn_resi") == "354340"
    assert diagnostico.codigo_municipal({"id_mn_resi": 3543402}, "id_mn_resi") == "354340"


def test_lista_registros_aceita_envelope_dengue():
    assert diagnostico.lista_registros({"dengue": [{"id_mn_resi": "354340"}]}) == [
        {"id_mn_resi": "354340"}
    ]


def test_lista_registros_aceita_lista_vazia():
    assert diagnostico.lista_registros({"dengue": []}) == []


def test_assinatura_e_deterministica_sem_expor_linha():
    row = {"id_mn_resi": "354340", "campo": "valor"}
    assert diagnostico.assinatura_linha(row) == diagnostico.assinatura_linha(row)
    assert len(diagnostico.assinatura_linha(row)) == 64


def test_diagnostico_avanca_offset_pelo_tamanho_da_pagina(monkeypatch):
    chamadas = []

    class Response:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            pass

        def json(self):
            return {"dengue": self.rows}

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, url, params, timeout):
            chamadas.append(params.copy())
            code = params["id_municip"]
            offset = params["offset"]
            if offset == 0:
                rows = [
                    {"id_municip": code, "id_mn_resi": "354340", "registro": 1},
                    {"id_municip": code, "id_mn_resi": "354340", "registro": 2},
                ]
            elif offset == 2:
                rows = [{"id_municip": code, "id_mn_resi": "354340", "registro": 3}]
            else:
                rows = []
            return Response(rows)

    monkeypatch.setattr(diagnostico.requests, "Session", Session)
    result = diagnostico.diagnosticar(2024, max_pages=3, page_size=2, pausa=0)

    assert len(chamadas) == 20
    assert [call["offset"] for call in chamadas[:2]] == [0, 2]
    assert chamadas[0]["id_municip"] == "350560"
    barrinha = result["resultados_por_municipio_notificador"]["Barrinha"]
    assert barrinha["registros_lidos"] == 3
    assert barrinha["registros_distintos_por_hash"] == 3
    assert barrinha["registros_repetidos_entre_paginas_ou_na_consulta"] == 0
    assert barrinha["varredura_completa"] is True
