import shutil
from pathlib import Path

import pytest

from pipeline.carga import carregar_arquivo
from pipeline.dimensoes import carregar_dimensoes

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LAYOUT = FIXTURES / "layout.xlsx"  # dicionário oficial do CAGED (documento público)
AMOSTRA = FIXTURES / "CAGEDMOV202510_amostra.txt"  # 1.000 linhas reais do arquivo de 2025-10


@pytest.fixture()
def amostra(tmp_path):
    """1.000 linhas reais de 2025-10 (mais o cabeçalho) e 1 duplicata exata de propósito."""
    destino = tmp_path / "CAGEDMOV202510.txt"
    with open(AMOSTRA, encoding="utf-8") as f:
        linhas = f.readlines()
    linhas.append(linhas[-1])  # duplicata exata: deve ser mantida
    destino.write_text("".join(linhas), encoding="utf-8")
    return destino


@pytest.fixture()
def banco(conn):
    carregar_dimensoes(conn, LAYOUT)
    return conn


def contar(conn):
    return conn.execute("SELECT count(*) FROM movimentacao").fetchone()[0]


def test_carrega_e_mantem_linhas_identicas(banco, amostra):
    assert carregar_arquivo(banco, amostra) == "carregado"
    assert contar(banco) == 1001


def test_rodar_duas_vezes_nao_duplica(banco, amostra):
    carregar_arquivo(banco, amostra)
    assert carregar_arquivo(banco, amostra) == "pulado"
    assert contar(banco) == 1001


def test_arquivo_republicado_substitui_sem_duplicar(banco, amostra):
    carregar_arquivo(banco, amostra)
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    amostra.write_text("".join(texto[:501]), encoding="utf-8")  # governo republicou menor
    assert carregar_arquivo(banco, amostra) == "atualizado"
    assert contar(banco) == 500


def test_falha_no_meio_nao_deixa_carga_pela_metade(banco, amostra):
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    texto[600] = texto[600].replace(";", ";XX;", 1)  # linha corrompida
    amostra.write_text("".join(texto), encoding="utf-8")
    with pytest.raises(Exception):
        carregar_arquivo(banco, amostra)
    assert contar(banco) == 0
    assert banco.execute("SELECT count(*) FROM carga_arquivo").fetchone()[0] == 0


def test_codigo_fora_da_dimensao_aborta_a_carga(banco, amostra):
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    cab = texto[0].strip().split(";")
    linha = texto[10].strip().split(";")
    linha[cab.index("uf")] = "77"  # UF que não existe no dicionário
    texto[10] = ";".join(linha) + chr(10)
    amostra.write_text("".join(texto), encoding="utf-8")
    with pytest.raises(ValueError, match="uf"):
        carregar_arquivo(banco, amostra)
    assert contar(banco) == 0
    assert banco.execute("SELECT count(*) FROM carga_arquivo").fetchone()[0] == 0


def test_salario_absurdo_vira_null_e_a_linha_e_mantida(banco, amostra):
    """Regressão: um salário de 7,05e+10 (erro da fonte) derrubava a carga inteira."""
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    cab = texto[0].strip().split(";")
    linha = texto[10].strip().split(";")
    linha[cab.index("salário")] = "7,05e+10"
    texto[10] = ";".join(linha) + chr(10)
    amostra.write_text("".join(texto), encoding="utf-8")
    assert carregar_arquivo(banco, amostra) == "carregado"
    assert contar(banco) == 1001  # nenhuma linha perdida
    assert banco.execute("SELECT count(*) FROM movimentacao WHERE salario IS NULL").fetchone()[0] >= 1


def test_view_so_conta_o_mov_e_bate_com_o_calculo_direto_dos_arquivos(banco, amostra):
    """A view do painel usa só o CAGEDMOV (critério do Ministério) e o CSV sem banco é equivalente."""
    import pandas as pd
    from pandas.testing import assert_frame_equal

    from pipeline.exportar import COLUNAS, indicadores_dos_arquivos

    carregar_arquivo(banco, amostra)
    fora_do_prazo = amostra.with_name("CAGEDFOR202510.txt")  # mesmo conteúdo, mas é o arquivo FOR
    fora_do_prazo.write_text(amostra.read_text(encoding="utf-8"), encoding="utf-8")
    carregar_arquivo(banco, fora_do_prazo)
    assert contar(banco) == 2002  # os dois arquivos estão no banco...

    banco.execute((Path(__file__).resolve().parent.parent / "sql" / "views" / "001_indicadores.sql")
                  .read_text(encoding="utf-8"))
    na_view = pd.DataFrame(
        banco.execute(f"SELECT {', '.join(COLUNAS)} FROM mv_indicadores").fetchall(), columns=COLUNAS
    ).sort_values(["mes", "estado", "setor"]).reset_index(drop=True)
    assert na_view["saldo"].sum() == banco.execute(
        "SELECT sum(saldo) FROM movimentacao WHERE arquivo_tipo = 'MOV'").fetchone()[0]  # ...mas a view só vê o MOV
    direto = indicadores_dos_arquivos(amostra.parent, LAYOUT)  # só procura CAGEDMOV*.txt
    assert_frame_equal(na_view, direto, check_dtype=False)
