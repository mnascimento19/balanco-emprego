"""Radar do Emprego: painel em Streamlit sobre o Novo CAGED.

Lê a materialized view mv_indicadores (mês x estado x setor). Execução:
    streamlit run app/app.py
"""
import os

import pandas as pd
import plotly.graph_objects as go
import psycopg
import streamlit as st

DB_URL = os.environ.get("DATABASE_URL", "postgresql://radar:radar@localhost:5432/radar")
POSITIVO, NEGATIVO = "#2a78d6", "#e34948"  # par divergente azul/vermelho: saldo positivo/negativo

st.set_page_config(page_title="Radar do Emprego", page_icon="📊", layout="wide")


def br(n) -> str:
    """Número no formato brasileiro (milhar com ponto), com sinal explícito para saldos."""
    return f"{int(n):,}".replace(",", ".")


def mes_legivel(m: str) -> str:
    return f"{m[4:]}/{m[:4]}"


@st.cache_data(ttl=300, show_spinner="Consultando o banco...")
def carregar() -> pd.DataFrame:
    with psycopg.connect(DB_URL) as conn:
        cur = conn.execute(
            "SELECT mes, estado, setor, admissoes, desligamentos, saldo FROM mv_indicadores"
        )
        colunas = [d.name for d in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=colunas)
    for c in ("admissoes", "desligamentos", "saldo"):
        df[c] = df[c].astype(int)
    return df


def barras(df: pd.DataFrame, rotulo: str, topo: int | None = None) -> go.Figure:
    """Barras horizontais de saldo, azul se positivo e vermelho se negativo."""
    d = df.groupby(rotulo, as_index=False)["saldo"].sum().sort_values("saldo")
    if topo:
        d = pd.concat([d.head(topo // 2), d.tail(topo - topo // 2)]).drop_duplicates()
    fig = go.Figure(go.Bar(
        x=d["saldo"], y=d[rotulo], orientation="h",
        marker_color=[POSITIVO if v >= 0 else NEGATIVO for v in d["saldo"]],
        text=[br(v) for v in d["saldo"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Saldo: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(320, 26 * len(d) + 80), margin=dict(l=0, r=40, t=10, b=0),
        xaxis=dict(title="Saldo de empregos (admissões − desligamentos)", zeroline=True, zerolinewidth=1),
        yaxis=dict(title=None), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


try:
    dados = carregar()
except Exception as e:  # banco fora do ar ou view ainda não criada
    st.error(f"Não consegui ler os dados: {e}")
    st.info("Suba o banco (`docker compose up -d`) e rode `python -m pipeline.cli views`.")
    st.stop()

st.title("📊 Radar do Emprego")
st.caption(
    "Saldo de empregos formais no Brasil (Novo CAGED). Saldo = admissões − desligamentos, "
    "contando exclusões declaradas. Mês = mês em que a informação foi declarada ao governo."
)

meses = sorted(dados["mes"].unique())
with st.sidebar:
    st.header("Filtros")
    mes = st.selectbox("Mês", meses, index=len(meses) - 1, format_func=mes_legivel)
    estados = st.multiselect("Estados", sorted(dados["estado"].unique()), placeholder="Todos")
    setores = st.multiselect("Setores", sorted(dados["setor"].unique()), placeholder="Todos")

filtrado = dados
if estados:
    filtrado = filtrado[filtrado["estado"].isin(estados)]
if setores:
    filtrado = filtrado[filtrado["setor"].isin(setores)]

atual = filtrado[filtrado["mes"] == mes]
anterior_mes = meses[meses.index(mes) - 1] if meses.index(mes) > 0 else None
anterior = filtrado[filtrado["mes"] == anterior_mes] if anterior_mes else None

c1, c2, c3 = st.columns(3)
delta = (
    f"{int(atual['saldo'].sum() - anterior['saldo'].sum()):+,}".replace(",", ".") + f" vs {mes_legivel(anterior_mes)}"
    if anterior is not None else None
)
c1.metric("Saldo de empregos", f"{int(atual['saldo'].sum()):+,}".replace(",", "."), delta)
c2.metric("Admissões", br(atual["admissoes"].sum()))
c3.metric("Desligamentos", br(atual["desligamentos"].sum()))

aba_setor, aba_uf, aba_tempo, aba_tabela = st.tabs(["Setores", "Estados", "Evolução", "Tabela"])

with aba_setor:
    st.subheader(f"Saldo por setor — {mes_legivel(mes)}")
    st.plotly_chart(barras(atual, "setor"), width="stretch")
    with st.expander("Top 3 setores por estado"):
        por = atual.groupby(["estado", "setor"], as_index=False)["saldo"].sum()
        por["posição"] = por.groupby("estado")["saldo"].rank(method="first", ascending=False).astype(int)
        top3 = por[por["posição"] <= 3].sort_values(["estado", "posição"])
        st.dataframe(top3, hide_index=True, width="stretch")

with aba_uf:
    st.subheader(f"Saldo por estado — {mes_legivel(mes)}")
    st.plotly_chart(barras(atual, "estado"), width="stretch")

with aba_tempo:
    st.subheader("Saldo mensal")
    serie = filtrado.groupby("mes", as_index=False)["saldo"].sum().sort_values("mes")
    if len(serie) < 2:
        st.info("Só há um mês carregado; a evolução aparece quando houver mais meses.")
    fig = go.Figure(go.Bar(
        x=[mes_legivel(m) for m in serie["mes"]], y=serie["saldo"],
        marker_color=[POSITIVO if v >= 0 else NEGATIVO for v in serie["saldo"]],
        hovertemplate="%{x}<br>Saldo: %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
        yaxis=dict(title="Saldo de empregos"), xaxis=dict(title=None, type="category"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width="stretch")

with aba_tabela:
    st.subheader("Dados do mês filtrado")
    tabela = atual.groupby(["estado", "setor"], as_index=False)[["admissoes", "desligamentos", "saldo"]].sum()
    st.dataframe(tabela.sort_values("saldo", ascending=False), hide_index=True, width="stretch")
