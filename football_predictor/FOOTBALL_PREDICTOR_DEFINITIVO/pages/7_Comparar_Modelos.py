import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

from data.loader import DataLoader
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel
from predictor.hybrid_model import HybridModel
from predictor.backtesting import FootballBacktester

st.set_page_config(page_title="Comparar Modelos & Backtesting", page_icon="⚖️", layout="wide")

st.title("⚖️ Comparativa de Modelos Predictivos & Backtesting")
st.markdown("""
Esta página permite comparar los 3 modelos predictivos (Poisson, Dixon-Coles y Hybrid) 
y ejecutar backtests históricos para medir su precisión.
""")

# Cargar datos
loader = DataLoader()
teams = loader.load_teams()
team_names = sorted([t["name"] for t in teams])

if len(team_names) < 2:
    st.warning("Necesitas al menos 2 equipos cargados para comparar modelos. Ve a 'Actualizar Datos'.")
    st.stop()

# Pestañas para organizar la interfaz
tab1, tab2, tab3 = st.tabs(["🏆 Comparar Modelos en Partido", "📊 Histórico de Backtests", "🔍 Ejecutar Backtest"])

# ------------------------------------------------------------------------------
# TAB 1: Comparar modelos en un partido específico
# ------------------------------------------------------------------------------
with tab1:
    st.header("Comparar Modelos en Partido")
    col1, col2 = st.columns(2)

    with col1:
        default_home_idx = team_names.index("Real Madrid") if "Real Madrid" in team_names else 0
        home_name = st.selectbox("Equipo Local", team_names, index=default_home_idx)
    with col2:
        default_away_idx = team_names.index("Manchester City") if "Manchester City" in team_names else min(1, len(team_names) - 1)
        away_name = st.selectbox("Equipo Visitante", team_names, index=default_away_idx)

    home = loader.get_team(home_name)
    away = loader.get_team(away_name)

    if home and away:
        model_p = PoissonModel()
        model_dc = DixonColesModel()
        model_hybrid = HybridModel()

        res_p = model_p.predict_match(home, away)
        res_dc = model_dc.predict_match(home, away)
        res_hybrid = model_hybrid.predict_match(home, away)

        # Métricas comparativas
        st.divider()
        m1, m2, m3 = st.columns(3)
        
        with m1:
            diff_draw_p = (res_dc["draw"] - res_p["draw"]) * 100
            st.metric("Prob. Empate (Dixon-Coles)", f"{res_dc['draw']:.1%}", f"{diff_draw_p:+.2f}% vs Poisson")
        
        with m2:
            diff_home_p = (res_dc["home_win"] - res_p["home_win"]) * 100
            st.metric("Victoria Local (Dixon-Coles)", f"{res_dc['home_win']:.1%}", f"{diff_home_p:+.2f}% vs Poisson")
        
        with m3:
            diff_away_p = (res_dc["away_win"] - res_p["away_win"]) * 100
            st.metric("Victoria Visitante (Dixon-Coles)", f"{res_dc['away_win']:.1%}", f"{diff_away_p:+.2f}% vs Poisson")

        # Gráfico de barras comparativo para TODOS los modelos
        labels = ["Victoria Local", "Empate", "Victoria Visitante"]
        vals_p = [res_p["home_win"], res_p["draw"], res_p["away_win"]]
        vals_dc = [res_dc["home_win"], res_dc["draw"], res_dc["away_win"]]
        vals_hybrid = [res_hybrid["home_win"], res_hybrid["draw"], res_hybrid["away_win"]]

        fig = go.Figure(data=[
            go.Bar(name='Poisson', x=labels, y=vals_p, marker_color='#185FA5'),
            go.Bar(name='Dixon-Coles', x=labels, y=vals_dc, marker_color='#993C1D'),
            go.Bar(name='Hybrid', x=labels, y=vals_hybrid, marker_color='#32A852')
        ])
        fig.update_layout(barmode='group', title=f"Probabilidades: {home_name} vs {away_name}", yaxis_tickformat='.1%')
        st.plotly_chart(fig, use_container_width=True)

        # Comparativa de matrices (heatmap)
        st.subheader("Diferencia en Matriz de Marcadores (Dixon-Coles - Poisson)")
        diff_matrix = res_dc["score_matrix"] - res_p["score_matrix"]
        
        fig_hm = go.Figure(data=go.Heatmap(
            z=diff_matrix[:6, :6],
            x=[str(i) for i in range(6)],
            y=[str(i) for i in range(6)],
            colorscale='RdBu',
            zmid=0,
            text=np.around(diff_matrix[:6, :6] * 100, 2),
            texttemplate="%{text}%",
        ))
        fig_hm.update_layout(
            title="Azul: Dixon-Coles predice más probable | Rojo: Poisson predice más probable",
            xaxis_title=f"Goles {away_name}",
            yaxis_title=f"Goles {home_name}"
        )
        st.plotly_chart(fig_hm, use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 2: Ver backtests históricos
# ------------------------------------------------------------------------------
with tab2:
    st.header("Histórico de Backtests")

    backtester = FootballBacktester()
    results = backtester.get_historical_results()

    if results:
        df = pd.DataFrame(results)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d/%m/%Y %H:%M")

        # Formatear columnas numéricas
        style_df = df.style.format({
            "accuracy": "{:.2%}",
            "f1_score": "{:.4f}",
            "brier_score": "{:.4f}"
        })

        st.dataframe(style_df, use_container_width=True)

        # Gráfico de accuracy por modelo
        fig_acc = go.Figure()
        for model in df["model_name"].unique():
            model_df = df[df["model_name"] == model].sort_values("season")
            fig_acc.add_trace(
                go.Scatter(x=model_df["season"], y=model_df["accuracy"], name=model, mode="lines+markers")
            )

        fig_acc.update_layout(title="Evolución de Accuracy por Modelo", yaxis_tickformat=".0%")
        st.plotly_chart(fig_acc, use_container_width=True)

    else:
        st.info("No hay backtests históricos aún. Ejecuta tu primer backtest en la pestaña '🔍 Ejecutar Backtest'!")

# ------------------------------------------------------------------------------
# TAB 3: Ejecutar backtests
# ------------------------------------------------------------------------------
with tab3:
    st.header("Ejecutar Backtest")

    season = st.selectbox("Temporada para backtest", ["2022-23", "2023-24"], index=0)
    model = st.selectbox("Modelo a testear", ["poisson", "dixon_coles", "hybrid", "todos"], index=3)

    if st.button("Ejecutar Backtest", type="primary"):
        with st.spinner("Ejecutando backtest... esto puede tardar unos segundos..."):
            backtester = FootballBacktester()
            metrics_list = []

            models_to_test = ["poisson", "dixon_coles", "hybrid"] if model == "todos" else [model]

            for model_name in models_to_test:
                try:
                    metrics = backtester.run_backtest(model_name, season)
                    if metrics:
                        backtester.save_backtest_result(metrics)
                        metrics_list.append(metrics)
                except Exception as e:
                    st.error(f"Error en backtest para {model_name}: {e}")

            if metrics_list:
                st.success("Backtest completado!")

                for metrics in metrics_list:
                    st.divider()
                    st.subheader(f"Resultados para {metrics['model_name']}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Accuracy", f"{metrics['accuracy']:.2%}")
                    c2.metric("F1-Score", f"{metrics['f1_score']:.4f}")
                    c3.metric("Brier Score", f"{metrics['brier_score']:.4f}")
