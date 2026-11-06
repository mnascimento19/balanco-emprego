import py7zr

from pipeline.coleta import extrair


def _fazer_7z(pasta, nome, conteudo):
    txt = pasta / f"{nome}.txt"
    txt.write_text(conteudo, encoding="utf-8")
    arq = pasta / f"{nome}.7z"
    with py7zr.SevenZipFile(arq, "w") as z:
        z.write(txt, txt.name)
    txt.unlink()
    return arq


def test_extrai_o_txt(tmp_path):
    arq = _fazer_7z(tmp_path, "CAGEDEXC202501", "a;b\n1;2\n")
    saida = extrair(arq, tmp_path / "out")
    assert saida.read_text(encoding="utf-8") == "a;b\n1;2\n"


def test_txt_vazio_de_tentativa_anterior_e_reextraido(tmp_path):
    """Regressão: um .txt de 0 bytes (extração interrompida) não pode ser reaproveitado."""
    arq = _fazer_7z(tmp_path, "CAGEDEXC202501", "a;b\n1;2\n")
    out = tmp_path / "out"
    out.mkdir()
    (out / "CAGEDEXC202501.txt").write_text("")  # sobra de uma falha
    assert extrair(arq, out).stat().st_size > 0


def test_nao_deixa_pasta_temporaria_para_tras(tmp_path):
    arq = _fazer_7z(tmp_path, "CAGEDEXC202501", "a;b\n1;2\n")
    out = tmp_path / "out"
    extrair(arq, out)
    assert [p.name for p in out.iterdir()] == ["CAGEDEXC202501.txt"]
