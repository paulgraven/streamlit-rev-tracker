# app.py
import streamlit as st
import pandas as pd
from datetime import date
from database import get_connection

st.set_page_config(layout="wide")
st.title("Weekly Revenue & EBITDA Forecast")

# ---------- Data Entry ----------
st.subheader("Submit Forecast")
financials = st.selectbox("Financials", ["Revenue", "EBITDA"])
region = st.selectbox("Region", ["USA", "Canada", "Europe", "India", "Australia", "Africa"])
week = st.date_input("Week", value=date.today())
flash_est = st.number_input("Flash Estimate", min_value=0.0, step=1000.0, format="%.2f")
actuals = st.number_input("Actuals", min_value=0.0, step=1000.0, format="%.2f")

def compute_metrics(flash_val: float, actual_val: float):
    fva = flash_val - actual_val
    pct_var = (fva / actual_val) if actual_val != 0 else None
    acc = max(0.0, 1.0 - abs(fva) / abs(actual_val)) if actual_val != 0 else 0.0
    return fva, pct_var, acc

if st.button("Submit"):
    fva, pct_var, acc = compute_metrics(flash_est, actuals)
    month_num = week.month
    year_num = week.year

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            # Insert row using EXACT quoted column names
            cur.execute(
                '''
                INSERT INTO revenue_forecast (
                    "Financials", "Region", "Week", "Flash Est", "Actuals",
                    "Flash vs Act", "% Variance", "Accuracy", "Month", "EOM"
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '')
                ''',
                (
                    financials, region, week, float(flash_est), float(actuals),
                    float(fva), None if pct_var is None else float(pct_var),
                    float(acc), month_num
                )
            )

            # Ensure exactly one EOM per Region×Month×Year
            cur.execute(
                '''
                UPDATE revenue_forecast
                SET "EOM" = ''
                WHERE "Region" = %s
                  AND DATE_PART('month', "Week") = %s
                  AND DATE_PART('year',  "Week") = %s
                ''',
                (region, month_num, year_num)
            )
            cur.execute(
                '''
                WITH mx AS (
                  SELECT MAX("Week") AS w
                  FROM revenue_forecast
                  WHERE "Region" = %s
                    AND DATE_PART('month', "Week") = %s
                    AND DATE_PART('year',  "Week") = %s
                )
                UPDATE revenue_forecast
                SET "EOM" = 'EOM'
                WHERE "Region" = %s
                  AND DATE_PART('month', "Week") = %s
                  AND DATE_PART('year',  "Week") = %s
                  AND "Week" = (SELECT w FROM mx)
                ''',
                (region, month_num, year_num, region, month_num, year_num)
            )

        st.success("Forecast submitted.")
    finally:
        conn.close()

# ---------- Data View ----------
conn = get_connection()
try:
    df = pd.read_sql_query(
        '''
        SELECT
          "Financials","Region","Week","Flash Est","Actuals",
          "Flash vs Act","% Variance","Accuracy","Month","EOM"
        FROM revenue_forecast
        ORDER BY "Week" DESC
        ''',
        conn
    )
finally:
    conn.close()

# Safe parsing for display
if "Week" in df.columns:
    df["Week"] = pd.to_datetime(df["Week"])

st.subheader("Forecast Table")
st.dataframe(df, use_container_width=True)

st.download_button(
    "Export to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="revenue_forecast.csv",
    mime="text/csv"
)