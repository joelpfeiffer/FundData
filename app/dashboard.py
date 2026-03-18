import os
os.makedirs("data", exist_ok=True)

from pipeline.database import init_db
init_db()

import streamlit as st
import sqlite3
import pandas as pd

from app.config import DB_PATH
from app.analytics import normalize, performance, volatility, sharpe_ratio
from pipeline.runner import run

# === Zorg dat data bestaat ===
conn = sqlite3.connect(DB_PATH)

try:
    count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
except:
    count = 0

conn.close()

if count == 0:
    run()

# === Dashboard ===
st.set_page_config(layout="wide")
st.title("📈 Funds Intelligence Dashboard")

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM prices", conn)
conn.close()

if df.empty:
    st.warning("Geen data")
    st.stop()

df["date"] = pd.to_datetime(df["date"])
pivot = df.pivot(index="date", columns="fund", values="price")

selected = st.multiselect("Fondsen", pivot.columns, default=list(pivot.columns)[:5])
pivot = pivot[selected]

norm = normalize(pivot)

st.subheader("📊 Groei")
st.line_chart(norm)

st.subheader("🏆 Performance")
st.dataframe(performance(norm))

st.subheader("⚡ Volatility")
st.dataframe(volatility(norm))

st.subheader("📉 Sharpe Ratio")
st.dataframe(sharpe_ratio(norm))

# 🔥 Bonus
best = performance(norm).index[0]
st.success(f"🏆 Beste fonds: {best}")
