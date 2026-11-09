"""Balanço do Emprego: painel em Streamlit sobre o Novo CAGED.

Lê a materialized view mv_indicadores (mês x estado x setor). Se o banco não estiver acessível
(caso da versão publicada na nuvem), usa o arquivo exportado por `python -m pipeline.cli exportar`.
Execução:
    streamlit run app/app.py
"""
import os
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_URL = os.environ.get("DATABASE_URL", "postgresql://radar:radar@localhost:5432/radar")
CSV = Path(os.environ.get("INDICADORES_CSV", Path(__file__).parent / "dados" / "indicadores.csv"))
POSITIVO, NEGATIVO = "#2a78d6", "#e34948"  # par divergente azul/vermelho: saldo positivo/negativo
TEXTO, GRADE = "#52514e", "rgba(0,0,0,0.08)"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Os nomes oficiais da CNAE são longos demais para um gráfico. A chave é o começo do nome, sem acento.
SETORES_CURTOS = {
    "administracao publica": "Administração pública",
    "agricultura": "Agropecuária e pesca",
    "agua": "Água, esgoto e resíduos",
    "alojamento": "Alojamento e alimentação",
    "artes": "Artes, cultura e esporte",
    "atividades administrativas": "Serviços administrativos",
    "atividades financeiras": "Finanças e seguros",
    "atividades imobiliarias": "Atividades imobiliárias",
    "atividades profissionais": "Serviços profissionais e técnicos",
    "comercio": "Comércio",
    "construcao": "Construção",
    "educacao": "Educação",
    "eletricidade": "Eletricidade e gás",
    "industrias extrativas": "Indústria extrativa",
    "industrias de transformacao": "Indústria de transformação",
    "informacao": "Informação e comunicação",
    "nao identificado": "Não identificado",
    "organismos": "Organismos internacionais",
    "outras atividades": "Outros serviços",
    "saude": "Saúde e serviços sociais",
    "servicos domesticos": "Serviços domésticos",
    "transporte": "Transporte e logística",
}

st.set_page_config(page_title="Balanço do Emprego", page_icon="📈", layout="wide")


def br(n) -> str:
    """Número no formato brasileiro (milhar com ponto)."""
    return f"{int(n):,}".replace(",", ".")


def com_sinal(n) -> str:
    return f"{int(n):+,}".replace(",", ".")


def mil(n) -> str:
    """Rótulo curto para gráficos: +114 mil."""
    n = int(n)
    return com_sinal(n) if abs(n) < 1000 else f"{round(n / 1000):+d} mil"


def mes_legivel(m: str) -> str:
    return f"{m[4:]}/{m[:4]}"


def mes_extenso(m: str) -> str:
    return f"{MESES[int(m[4:]) - 1]} de {m[:4]}"


def setor_curto(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    for prefixo, curto in SETORES_CURTOS.items():
        if sem_acento.startswith(prefixo):
            return curto
    return nome


@st.cache_data(ttl=300, show_spinner="Carregando os dados...")
def carregar() -> tuple[pd.DataFrame, str]:
    """Banco, se estiver acessível; senão o arquivo exportado. Devolve também a origem."""
    try:
        import psycopg  # fica de fora das dependências da versão publicada

        with psycopg.connect(DB_URL, connect_timeout=3) as conn:
            cur = conn.execute(
                "SELECT mes, estado, setor, admissoes, desligamentos, saldo FROM mv_indicadores"
            )
            df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        origem = "banco"
    except Exception:
        if not CSV.exists():
            raise
        df, origem = pd.read_csv(CSV, dtype={"mes": str}), "arquivo"
    for c in ("admissoes", "desligamentos", "saldo"):
        df[c] = df[c].astype(int)
    df["setor"] = df["setor"].map(setor_curto)
    df["estado"] = df["estado"].replace({"Minas gerais": "Minas Gerais"})  # grafia do dicionário oficial
    return df, origem


def estilo(fig: go.Figure, altura: int) -> go.Figure:
    fig.update_layout(
        height=altura, margin=dict(l=0, r=48, t=8, b=0), showlegend=False, bargap=0.38,
        font=dict(color=TEXTO, size=13),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def barras(df: pd.DataFrame, rotulo: str) -> go.Figure:
    """Barras horizontais de saldo, azul se positivo e vermelho se negativo (maior no topo)."""
    d = df.groupby(rotulo, as_index=False)["saldo"].sum().sort_values("saldo")
    fig = go.Figure(go.Bar(
        x=d["saldo"], y=d[rotulo], orientation="h",
        marker_color=[POSITIVO if v >= 0 else NEGATIVO for v in d["saldo"]],
        text=[com_sinal(v) for v in d["saldo"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Saldo: %{x:,.0f}<extra></extra>",
    ))
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=True, zerolinecolor=GRADE)
    fig.update_yaxes(title=None, automargin=True)
    return estilo(fig, max(300, 30 * len(d) + 40))


def mostrar(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


try:
    dados, origem = carregar()
except Exception as e:  # sem banco e sem arquivo exportado
    st.error(f"Não consegui ler os dados: {e}")
    st.info("Suba o banco (`docker compose up -d`) e rode `python -m pipeline.cli views`.")
    st.stop()

meses = sorted(dados["mes"].unique())

st.title("Balanço do Emprego")
st.caption(
    f"Quantos empregos formais o Brasil abriu ou fechou, mês a mês. "
    f"Novo CAGED, dados até {mes_extenso(meses[-1])}."
)

f1, f2, f3 = st.columns([1, 2, 2])
mes = f1.selectbox("Mês", meses, index=len(meses) - 1, format_func=mes_legivel)
estados = f2.multiselect("Estados", sorted(dados["estado"].unique()), placeholder="Todos os estados")
setores = f3.multiselect("Setores", sorted(dados["setor"].unique()), placeholder="Todos os setores")

filtrado = dados
if estados:
    filtrado = filtrado[filtrado["estado"].isin(estados)]
if setores:
    filtrado = filtrado[filtrado["setor"].isin(setores)]

atual = filtrado[filtrado["mes"] == mes]
anterior_mes = meses[meses.index(mes) - 1] if meses.index(mes) > 0 else None
anterior = filtrado[filtrado["mes"] == anterior_mes] if anterior_mes else None

saldo = int(atual["saldo"].sum())
variacao = int(saldo - anterior["saldo"].sum()) if anterior is not None else None

if saldo > 0:
    resultado = f"abriu **{br(saldo)} empregos formais a mais do que fechou**"
elif saldo < 0:
    resultado = f"fechou **{br(-saldo)} empregos formais a mais do que abriu**"
else:
    resultado = "abriu **tantos empregos formais quanto fechou**"
if not estados and not setores:
    sujeito = "o Brasil"
elif len(estados) == 1 and not setores:
    sujeito = estados[0]
elif len(setores) == 1 and not estados:
    sujeito = f"o setor {setores[0]}"
else:
    sujeito = "o recorte escolhido"
frase = f"Em {mes_extenso(mes)}, {sujeito} {resultado}"
if variacao == 0:
    frase += f", o mesmo resultado de {mes_extenso(anterior_mes)}"
elif variacao is not None:
    frase += f", {br(abs(variacao))} {'a mais' if variacao > 0 else 'a menos'} que em {mes_extenso(anterior_mes)}"
st.markdown(f"### {frase}.")

c1, c2, c3 = st.columns(3)
adm, desl = int(atual["admissoes"].sum()), int(atual["desligamentos"].sum())


def vs_anterior(var) -> str | None:
    return f"{com_sinal(var)} vs {mes_legivel(anterior_mes)}" if anterior is not None else None


c1.metric("Saldo de empregos", com_sinal(saldo), vs_anterior(variacao), border=True)
c2.metric("Admissões", br(adm), vs_anterior(adm - int(anterior["admissoes"].sum())) if anterior is not None else None,
          border=True)
c3.metric("Desligamentos", br(desl),
          vs_anterior(desl - int(anterior["desligamentos"].sum())) if anterior is not None else None,
          delta_color="inverse", border=True)  # mais desligamentos é pior: aumento fica vermelho

aba_setor, aba_uf, aba_tempo, aba_tabela = st.tabs(["Por setor", "Por estado", "Evolução", "Tabela"])

with aba_setor:
    st.caption(f"Saldo por setor em {mes_legivel(mes)}")
    mostrar(barras(atual, "setor"))
    with st.expander("Os 3 setores que mais geraram emprego em cada estado"):
        por = atual.groupby(["estado", "setor"], as_index=False)["saldo"].sum()
        por["posição"] = por.groupby("estado")["saldo"].rank(method="first", ascending=False).astype(int)
        top3 = por[por["posição"] <= 3].sort_values(["estado", "posição"])
        top3.columns = ["Estado", "Setor", "Saldo", "Posição"]
        st.dataframe(top3[["Estado", "Posição", "Setor", "Saldo"]], hide_index=True, width="stretch",
                     column_config={"Saldo": st.column_config.NumberColumn(format="localized")})

with aba_uf:
    st.caption(f"Saldo por estado em {mes_legivel(mes)}")
    mostrar(barras(atual, "estado"))

with aba_tempo:
    st.caption("Saldo mensal de empregos formais")
    serie = filtrado.groupby("mes", as_index=False)["saldo"].sum().sort_values("mes")
    fig = go.Figure(go.Bar(
        x=[mes_legivel(m) for m in serie["mes"]], y=serie["saldo"],
        marker_color=[POSITIVO if v >= 0 else NEGATIVO for v in serie["saldo"]],
        text=[mil(v) for v in serie["saldo"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>Saldo: %{y:,.0f}<extra></extra>",
    ))
    fig.update_xaxes(title=None, type="category")
    passo = 200_000 if serie["saldo"].abs().max() > 300_000 else 100_000
    marcas = list(range(int(serie["saldo"].min() // passo) * passo, int(serie["saldo"].max() // passo + 2) * passo, passo))
    fig.update_yaxes(title=None, showgrid=True, gridcolor=GRADE, zeroline=True, zerolinecolor=GRADE,
                     tickvals=marcas, ticktext=["0" if v == 0 else mil(v) for v in marcas])
    mostrar(estilo(fig, 380))
    if len(serie) < 2:
        st.info("Só há um mês nos dados; a evolução aparece quando houver mais meses.")
    if any(m.endswith("12") for m in serie["mes"]):
        st.caption("Dezembro costuma fechar no negativo: é um padrão sazonal do emprego formal no Brasil.")

with aba_tabela:
    st.caption(f"Dados de {mes_legivel(mes)}, por estado e setor")
    tabela = atual.groupby(["estado", "setor"], as_index=False)[["admissoes", "desligamentos", "saldo"]].sum()
    tabela.columns = ["Estado", "Setor", "Admissões", "Desligamentos", "Saldo"]
    numero = st.column_config.NumberColumn(format="localized")
    st.dataframe(tabela.sort_values("Saldo", ascending=False), hide_index=True, width="stretch",
                 column_config={"Admissões": numero, "Desligamentos": numero, "Saldo": numero})

nota_origem = (
    f"Dados exportados do banco, com último mês em {mes_legivel(dados['mes'].max())}."
    if origem == "arquivo" else "Dados lidos do banco local."
)
st.divider()
st.caption(
    "Fonte: Novo CAGED, Ministério do Trabalho e Emprego. Saldo = admissões − desligamentos, calculado "
    "sobre o arquivo de movimentações declaradas no prazo (CAGEDMOV), o mesmo critério dos números "
    f"divulgados pelo Ministério. {nota_origem} Código em github.com/mnascimento19/balanco-emprego."
)
