from __future__ import annotations

import sqlite3
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

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
        "site", "title", "price_chf", "surface_m2", "district",
        "possible_changing_room", "score", "status", "url"
    ]],
    use_container_width=True,
)

m = folium.Map(location=[46.2044, 6.1432], zoom_start=12)
for _, row in filtered.iterrows():
    district = row.get("district")
    if district in DISTRICT_COORDS:
        lat, lon = DISTRICT_COORDS[district]
        popup = f"{row['title']}<br>{row.get('price_chf')} CHF<br>{row.get('surface_m2')} m²<br>Score {row.get('score')}"
        folium.Marker([lat, lon], popup=popup, tooltip=district).add_to(m)

st_folium(m, width=1200, height=500)
