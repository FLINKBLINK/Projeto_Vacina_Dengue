"""Testes para extração segura de linhas do JSON da API oficial."""
import pytest

from scripts.inspecionar_esquema_api import extrair_lista


@pytest.mark.parametrize(
    "payload, esperado",
    [
        ([{"id": 1}], [{"id": 1}]),
        ({"data": [{"id": 1}]}, [{"id": 1}]),
        ({"dengue": [{"id": 1}, "ignorar", None]}, [{"id": 1}]),
        ({"dengue": []}, []),
        ({"results": [{"id": 1}]}, [{"id": 1}]),
    ],
)
def test_extrair_lista_reconhece_formatos_comuns(payload, esperado):
    # O envelope SINAN conhecido é {"dengue": [...]}.
    assert extrair_lista(payload) == esperado


def test_extrair_lista_rejeita_formato_desconhecido_sem_vazar_payload():
    with pytest.raises(ValueError, match="Formato JSON não reconhecido"):
        extrair_lista({"mensagem": "formato inesperado", "detalhe": {"x": 1}})
