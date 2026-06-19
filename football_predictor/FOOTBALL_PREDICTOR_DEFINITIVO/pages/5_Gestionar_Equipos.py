"""
pages/5_Gestionar_Equipos.py
CRUD completo para añadir/editar/eliminar equipos y jugadores.
"""
import streamlit as st

from data.loader import DataLoader
from utils import DataValidator

st.set_page_config(page_title="Gestionar Datos", page_icon="⚙️", layout="wide")
st.title("⚙️ Gestionar Equipos y Jugadores")
st.caption("Añade, edita o elimina registros — los cambios persisten en los JSON.")

loader = DataLoader()

tab1, tab2, tab3 = st.tabs(["🏟️ Equipos", "⚽ Añadir jugador", "🗑️ Eliminar equipo"])

# ------------------------------------------------------------------ #
# EQUIPOS
# ------------------------------------------------------------------ #
with tab1:
    st.subheader("Equipos registrados")
    df = loader.teams_df()
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Añadir / Actualizar equipo")
    with st.form("team_form"):
        c1, c2 = st.columns(2)
        name    = c1.text_input("Nombre del equipo *")
        country = c2.text_input("País (código 3 letras, ej: ESP)")
        league  = c1.text_input("Liga")
        attack  = c1.number_input("Media goles anotados/partido", 0.5, 5.0, 1.5, 0.05)
        defense = c2.number_input("Media goles encajados/partido", 0.2, 4.0, 1.2, 0.05)
        ucl_t   = c1.number_input("Títulos UCL", 0, 20, 0)
        rank    = c2.number_input("Ranking histórico UCL", 1, 999, 100)
        submitted = st.form_submit_button("💾 Guardar equipo", type="primary")
        if submitted:
            if not name:
                st.error("El nombre es obligatorio.")
            elif not DataValidator.validate_team({"name": name, "country": country, "league": league, "attack": attack, "defense": defense}):
                st.error("⚠️ Datos inválidos: verifica que el ataque esté entre 0 y 5, y la defensa entre 0 y 3.")
            else:
                loader.add_or_update_team({
                    "name": name, "country": country, "league": league,
                    "attack": attack, "defense": defense,
                    "ucl_titles": ucl_t, "rank": rank,
                })
                st.success(f"✅ Equipo **{name}** guardado correctamente.")
                st.rerun()

# ------------------------------------------------------------------ #
# AÑADIR JUGADOR
# ------------------------------------------------------------------ #
with tab2:
    st.subheader("Añadir / Actualizar jugador")
    pos_type = st.selectbox("Tipo de jugador",
                             ["Delantero / Centrocampista", "Portero", "Defensa"])

    with st.form("player_form"):
        p_name = st.text_input("Nombre *")
        p_team = st.text_input("Equipo *")
        p_mp   = st.number_input("Partidos jugados", 1, 50, 10)

        if pos_type == "Delantero / Centrocampista":
            c1, c2 = st.columns(2)
            goals    = c1.number_input("Goles anotados", 0, 50, 5)
            shots_a  = c1.number_input("Disparos totales", 1, 100, 20)
            shots_t  = c2.number_input("Disparos a puerta", 0, 80, 10)
            assists  = c2.number_input("Asistencias", 0, 30, 2)
            pos_val  = st.selectbox("Posición detallada",
                                     ["striker", "midfielder"])
        elif pos_type == "Portero":
            c1, c2 = st.columns(2)
            saves  = c1.number_input("Paradas por partido", 0.0, 10.0, 3.0, 0.1)
            gc     = c2.number_input("Goles encajados por partido", 0.0, 5.0, 1.0, 0.1)
            cs     = c1.number_input("Porterías a cero", 0, 20, 2)
        else:
            c1, c2 = st.columns(2)
            br    = c1.number_input("Balones recup. por partido", 0.0, 15.0, 6.0, 0.1)
            tack  = c2.number_input("Entradas por partido", 0.0, 10.0, 2.0, 0.1)
            tw    = c1.number_input("Entradas exitosas por partido", 0.0, 10.0, 1.5, 0.1)

        submitted_p = st.form_submit_button("💾 Guardar jugador", type="primary")
        if submitted_p:
            if not p_name or not p_team:
                st.error("Nombre y equipo son obligatorios.")
            else:
                if pos_type == "Delantero / Centrocampista":
                    payload = {
                        "name": p_name, "team": p_team,
                        "position": pos_val, "matches_played": p_mp,
                        "goals": goals, "shots_attempted": shots_a,
                        "shots_on_target": shots_t, "assists": assists,
                    }
                    loader.add_or_update_player(payload, "players")
                elif pos_type == "Portero":
                    payload = {
                        "name": p_name, "team": p_team,
                        "matches_played": p_mp,
                        "saves": saves, "goals_conceded": gc,
                        "clean_sheets": cs,
                    }
                    loader.add_or_update_player(payload, "goalkeepers")
                else:
                    payload = {
                        "name": p_name, "team": p_team,
                        "matches_played": p_mp,
                        "balls_recovered": br, "tackles": tack,
                        "tackles_won": tw,
                    }
                    loader.add_or_update_player(payload, "defenders")
                st.success(f"✅ Jugador **{p_name}** guardado.")
                st.rerun()

# ------------------------------------------------------------------ #
# ELIMINAR EQUIPO
# ------------------------------------------------------------------ #
with tab3:
    st.subheader("Eliminar equipo")
    teams = loader.load_teams()
    if not teams:
        st.info("No hay equipos registrados para eliminar.")
        st.stop()
    del_name = st.selectbox("Selecciona equipo a eliminar",
                             [t["name"] for t in teams])
    if st.button("🗑️ Eliminar", type="secondary"):
        ok = loader.delete_team(del_name)
        if ok:
            st.success(f"Equipo **{del_name}** eliminado.")
            st.rerun()
        else:
            st.error("No se encontró el equipo.")
