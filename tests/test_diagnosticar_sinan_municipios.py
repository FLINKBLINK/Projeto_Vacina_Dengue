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


def test_diagnostico_consulta_cada_municipio_e_detecta_repeticao(monkeypatch):
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
                rows = [{"id_municip": code, "id_mn_resi": "354340"}]
            else:
                rows = []
            return Response(rows)

    monkeypatch.setattr(diagnostico.requests, "Session", Session)
    result = diagnostico.diagnosticar(2024, max_pages=2, page_size=2, pausa=0)
    assert len(chamadas) == len(diagnostico.MUNICIPIOS)
    assert chamadas[0]["offset"] == 0
    assert chamadas[0]["id_municip"] == "350560"
    assert result["resultados_por_municipio_notificador"]["Barrinha"]["registros_lidos"] == 1
    assert result["resultados_por_municipio_notificador"]["Barrinha"]["varredura_completa"] is True
