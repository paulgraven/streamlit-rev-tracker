import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import get_connection
from datetime import date

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

    with get_connection() as conn:
        # Insert the row using EXACT column names (quoted identifiers)
        insert_sql = text("""
            INSERT INTO revenue_forecast (
                "Financials", "Region", "Week", "Flash Est", "Actuals",
                "Flash vs Act", "% Variance", "Accuracy", "Month", "EOM"
            ) VALUES (
                :financials, :region, :week, :flash_est, :actuals,
                :fva, :pct_var, :acc, :month_num, ''
            )
        """)
        conn.execute(insert_sql, {
            "financials": financials,
            "region": region,
            "week": week,
            "flash_est": float(flash_est),
            "actuals": float(actuals),
            "fva": float(fva),
            "pct_var": float(pct_var) if pct_var is not None else None,
            "acc": float(acc),
            "month_num": month_num
        })

        # Ensure exactly one EOM per Region x Month x Year:
        # 1) Clear existing EOM for this Region/Month/Year
        clear_eom = text("""
            UPDATE revenue_forecast
            SET "EOM" = ''
            WHERE "Region" = :region
              AND DATE_PART('month', "Week") = :m
              AND DATE_PART('year', "Week")  = :y
        """)
        conn.execute(clear_eom, {"region": region, "m": month_num, "y": year_num})

        # 2) Mark the max Week in that Region/Month/Year as EOM
        set_eom = text("""
            WITH mx AS (
              SELECT MAX("Week") AS w
              FROM revenue_forecast
              WHERE "Region" = :region
                AND DATE_PART('month', "Week") = :m
                AND DATE_PART('year', "Week")  = :y
            )
            UPDATE revenue_forecast
            SET "EOM" = 'EOM'
            WHERE "Region" = :region
              AND DATE_PART('month', "Week") = :m
              AND DATE_PART('year', "Week")  = :y
              AND "Week" = (SELECT w FROM mx)
        """)
        conn.execute(set_eom, {"region": region, "m": month_num, "y": year_num})

        conn.commit()

    st.success("Forecast submitted.")

# ---------- Data View ----------
with get_connection() as conn:
    df = pd.read_sql(
        '''
        SELECT
          "Financials","Region","Week","Flash Est","Actuals",
          "Flash vs Act","% Variance","Accuracy","Month","EOM"
        FROM revenue_forecast
        ORDER BY "Week" DESC
        ''',
        conn
    )

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