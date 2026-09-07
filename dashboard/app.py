from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timezone

import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from storage.database import Database

DISTRICT_COORDS = {
    "Champel": (46.1903, 6.1546),
    "Eaux-Vives": (46.2013, 6.1604),
    "Rive": (46.2023, 6.1545),
    "Rives": (46.2023, 6.1545),
    "Plainpalais": (46.1980, 6.1428),
    "Jonction": (46.1983, 6.1317),
    "Carouge": (46.1815, 6.1399),
    "Acacias": (46.1910, 6.1324),
}

st.set_page_config(page_title="Geneva Gym Scanner", layout="wide")
st.title("Geneva Gym Scanner")

conn = sqlite3.connect("data/listings.db")
df = pd.read_sql_query("SELECT * FROM listings ORDER BY score DESC, last_seen_at DESC", conn)

if df.empty:
    st.warning("Aucune donnée pour l'instant.")
    st.stop()

# Historique de prix (annonce initiale vs prix le plus recent) -- une seule
# requete groupee (voir Database.price_history_summary, meme raison que dans
# site_generator.py : eviter le N+1 sur une table qui grandit a chaque scan).
_db = Database("data/listings.db")
# Une base existante (comme data/listings.db deja committee par le scan
# quotidien) n'a pas forcement la table price_history si elle a ete creee
# avant son ajout -- init_db() est idempotent (CREATE TABLE IF NOT EXISTS) et
# la cree si besoin, sans toucher aux donnees existantes de `listings`.
_db.init_db()
_price_summary = _db.price_history_summary()
df["initial_price_chf"] = df["id"].map(lambda i: _price_summary.get(i, {}).get("first_price_chf"))
df["price_dropped"] = df["id"].map(lambda i: bool(_price_summary.get(i, {}).get("price_dropped")))


def _days_listed(first_seen_at) -> int | None:
    if not first_seen_at:
        return None
    try:
        first_seen = datetime.strptime(first_seen_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return max(0, (datetime.now(timezone.utc) - first_seen).days)


df["days_listed"] = df["first_seen_at"].map(_days_listed)

status = st.multiselect("Status", sorted(df["status"].dropna().unique().tolist()), default=["active"])
districts = st.multiselect("Quartiers", sorted(df["district"].dropna().unique().tolist()), default=sorted(df["district"].dropna().unique().tolist()))
max_price = st.slider("Loyer max", min_value=0, max_value=10000, value=2000, step=100)
min_surface = st.slider("Surface min", min_value=0, max_value=1000, value=70, step=5)

filtered = df.copy()
filtered = filtered[filtered["status"].isin(status)]
filtered = filtered[filtered["price_chf"].fillna(10**9) <= max_price]
filtered = filtered[filtered["surface_m2"].fillna(0) >= min_surface]
if districts:
    filtered = filtered[filtered["district"].isin(districts)]

st.dataframe(
    filtered[[
        "site", "title", "price_chf", "initial_price_chf", "price_dropped",
        "surface_m2", "district", "possible_changing_room", "days_listed",
        "score", "status", "url"
    ]],
    use_container_width=True,
    column_config={
        "days_listed": st.column_config.NumberColumn("Jours en ligne"),
        "initial_price_chf": st.column_config.NumberColumn("Prix initial (CHF)"),
        "price_dropped": st.column_config.CheckboxColumn("Prix en baisse"),
    },
)

st.subheader("Annonces en ligne depuis le plus longtemps")
st.caption("Un bien qui traine depuis longtemps est un vrai levier de negociation.")
st.dataframe(
    filtered[filtered["status"] == "active"]
        .sort_values("days_listed", ascending=False)
        [["title", "days_listed", "price_chf", "district", "url"]]
        .head(10),
    use_container_width=True,
)

st.subheader("Historique de prix d'une annonce")
selected_title = st.selectbox(
    "Choisir une annonce", options=filtered["title"].tolist(), index=None,
    placeholder="Selectionner une annonce pour voir l'evolution de son prix",
)
if selected_title:
    selected_id = filtered.loc[filtered["title"] == selected_title, "id"].iloc[0]
    history = _db.price_history_for(selected_id)
    if len(history) > 1:
        hist_df = pd.DataFrame(history).rename(columns={"price_chf": "Prix (CHF)", "recorded_at": "Date"})
        st.line_chart(hist_df.set_index("Date")["Prix (CHF)"])
    else:
        st.caption("Un seul prix observe jusqu'ici pour cette annonce -- pas encore d'historique.")

st.subheader("Carte des annonces")
st.caption(
    "Position approximative (centre du quartier + dispersion aleatoire) -- "
    "les adresses exactes ne sont pas geocodees, voir CLAUDE.md."
)
m = folium.Map(location=[46.2044, 6.1432], zoom_start=12)
cluster = MarkerCluster().add_to(m)
rng = random.Random(0)  # seed fixe : la dispersion reste stable d'un refresh a l'autre
for _, row in filtered.iterrows():
    district = row.get("district")
    if district in DISTRICT_COORDS:
        lat, lon = DISTRICT_COORDS[district]
        # Un marker par ANNONCE plutot qu'un seul par quartier (comme avant) --
        # legere dispersion aleatoire pour que les markers d'un meme quartier
        # ne se superposent pas exactement.
        lat += rng.uniform(-0.003, 0.003)
        lon += rng.uniform(-0.003, 0.003)
        price_txt = f"{row.get('price_chf')} CHF" if row.get("price_chf") is not None else "Prix non publie"
        popup = (
            f"<b>{row['title']}</b><br>{price_txt}<br>{row.get('surface_m2')} m²"
            f"<br>Score {row.get('score')}"
            f"{'<br>Jours en ligne: ' + str(int(row['days_listed'])) if pd.notna(row.get('days_listed')) else ''}"
            f"<br><a href='{row['url']}' target='_blank'>Voir l'annonce</a>"
        )
        folium.Marker([lat, lon], popup=popup, tooltip=row["title"]).add_to(cluster)

st_folium(m, width=1200, height=500)
