# app.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import get_connection
from datetime import date

st.set_page_config(layout="wide")
st.title("Weekly Revenue & EBITDA Forecast")

# ------------- Data Entry -------------
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

    with get_connection() as conn:
        # Determine EOM by comparing to current max "Week" for the same calendar month
        max_week = conn.execute(
            text('SELECT MAX("Week") FROM revenue_forecast WHERE DATE_PART(\'month\',"Week") = :m'),
            {"m": month_num}
        ).scalar()

        eom_flag = "EOM" if (max_week is None or pd.to_datetime(week) >= pd.to_datetime(max_week)) else ""

        insert_sql = text("""
            INSERT INTO revenue_forecast (
                "Financials", "Region", "Week", "Flash Est", "Actuals",
                "Flash vs Act", "% Variance", "Accuracy", "Month", "EOM"
            )
            VALUES (
                :financials, :region, :week, :flash_est, :actuals,
                :fva, :pct_var, :acc, :month_num, :eom_flag
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
            "month_num": month_num,
            "eom_flag": eom_flag
        })
        conn.commit()

    st.success("Forecast submitted.")

# ------------- Data View -------------
with get_connection() as conn:
    df = pd.read_sql('SELECT * FROM revenue_forecast', conn)

# Ensure correct types/derived values for display only (columns already exist in DB)
if "Week" in df.columns:
    df["Week"] = pd.to_datetime(df["Week"])

# (Optional) recompute EOM for display consistency
if all(col in df.columns for col in ["Region", "Week"]):
    disp = df.copy()
    disp["Month"] = disp["Week"].dt.month
    latest = disp.groupby(["Month"])["Week"].transform("max")
    disp.loc[:, "EOM"] = (disp["Week"] == latest).map({True: "EOM", False: ""})
else:
    disp = df

st.subheader("Forecast Table")
st.dataframe(disp, use_container_width=True)

st.download_button(
    "Export to CSV",
    disp.to_csv(index=False).encode("utf-8"),
    file_name="revenue_forecast.csv",
    mime="text/csv"
)