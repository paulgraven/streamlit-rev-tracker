import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from database import get_engine

st.set_page_config(layout="wide")
st.title("Weekly Revenue & EBITDA Forecast")

engine = get_engine()

# ---- Form ----
st.subheader("Submit Forecast")
financials = st.selectbox("Financials", ["Revenue", "EBITDA"])
region     = st.selectbox("Region",     ["USA","Canada","Europe","India","Australia","Africa"])
week       = st.date_input("Week", value=date.today())
flash_est  = st.number_input("Flash Estimate", min_value=0.0, step=1000.0, format="%.2f")
actuals    = st.number_input("Actuals",       min_value=0.0, step=1000.0, format="%.2f")

def metrics(flash, actual):
    fva = flash - actual
    pct = (fva / actual) if actual != 0 else None
    acc = max(0.0, 1.0 - abs(fva) / abs(actual)) if actual != 0 else 0.0
    return fva, pct, acc

if st.button("Submit"):
    fva, pct, acc = metrics(flash_est, actuals)
    m = week.month
    y = week.year

    with engine.begin() as conn:
        # Insert computed fields
        conn.execute(
            text("""
                INSERT INTO revenue_forecast
                (financials, region, week, flash_est, actuals,
                 flash_vs_act, pct_variance, accuracy, month, eom)
                VALUES
                (:financials, :region, :week, :flash_est, :actuals,
                 :fva, :pct, :acc, :month, '')
            """),
            {
                "financials": financials, "region": region, "week": week,
                "flash_est": float(flash_est), "actuals": float(actuals),
                "fva": float(fva), "pct": (None if pct is None else float(pct)),
                "acc": float(acc), "month": m
            }
        )
        # Exactly one EOM per region x month x year
        conn.execute(
            text("""
                UPDATE revenue_forecast
                   SET eom = ''
                 WHERE region = :r
                   AND date_part('month', week) = :m
                   AND date_part('year',  week) = :y
            """), {"r": region, "m": m, "y": y}
        )
        conn.execute(
            text("""
                WITH mx AS (
                  SELECT MAX(week) AS w
                    FROM revenue_forecast
                   WHERE region = :r
                     AND date_part('month', week) = :m
                     AND date_part('year',  week) = :y
                )
                UPDATE revenue_forecast
                   SET eom = 'EOM'
                 WHERE region = :r
                   AND date_part('month', week) = :m
                   AND date_part('year',  week) = :y
                   AND week = (SELECT w FROM mx)
            """), {"r": region, "m": m, "y": y}
        )

    st.success("Saved.")

# ---- Table ----
with engine.connect() as conn:
    df = pd.read_sql_query(
        text("""
            SELECT financials, region, week, flash_est, actuals,
                   flash_vs_act, pct_variance, accuracy, month, eom
              FROM revenue_forecast
             ORDER BY week DESC
        """),
        conn,
        params={}
    )

if not df.empty:
    df["week"] = pd.to_datetime(df["week"])
    df = df.rename(columns={
        "financials":"Financials","region":"Region","week":"Week",
        "flash_est":"Flash Est","actuals":"Actuals",
        "flash_vs_act":"Flash vs Act","pct_variance":"% Variance",
        "accuracy":"Accuracy","month":"Month","eom":"EOM"
    })

st.subheader("Forecast Table")
st.dataframe(df, use_container_width=True)

st.download_button(
    "Export to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="revenue_forecast.csv",
    mime="text/csv"
)