from fastapi import FastAPI
import sqlite3
import pandas as pd
from app.config import DB_PATH

app = FastAPI()

@app.get("/prices")
def get_prices():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM prices", conn)
    conn.close()
    return df.to_dict(orient="records")
