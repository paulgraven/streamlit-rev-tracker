import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import get_connection
from datetime import date

st.set_page_config(layout="wide")
st.title("Revenue & EBITDA Forecast Tracker")

# ---------- Form to Submit Forecast ----------
st.subheader("Submit Forecast")
region = st.selectbox("Region", ["USA", "Canada", "Europe", "India", "Australia", "Africa"])
week = st.date_input("Week", value=date.today())
flash_est = st.number_input("Flash Estimate", min_value=0.0, step=1000.0)
actuals = st.number_input("Actuals", min_value=0.0, step=1000.0)

if st.button("Submit"):
    fva = flash_est - actuals
    pct_var = fva / actuals if actuals != 0 else None
    acc = max(0, 1 - abs(fva) / abs(actuals)) if actuals != 0 else 0
    month = week.month

    with get_connection() as conn:
        insert_query = text('''
            INSERT INTO revenue_forecast (
                Region, Week, "Flash Est", Actuals, "Flash vs Act", "% Variance", Accuracy, Month, EOM
            ) VALUES (
                :region, :week, :flash_est, :actuals, :fva, :pct_var, :acc, :month, :eom
            )
        ''')

        # Check if this is the last week of the month
        existing = pd.read_sql("SELECT * FROM revenue_forecast WHERE Region = :region", conn, params={"region": region})
        existing["Week"] = pd.to_datetime(existing["Week"])
        latest_week = existing[existing["Week"].dt.month == week.month]["Week"].max()
        eom_flag = "EOM" if pd.isna(latest_week) or week >= latest_week else ""

        conn.execute(insert_query, {
            "region": region,
            "week": week,
            "flash_est": flash_est,
            "actuals": actuals,
            "fva": fva,
            "pct_var": pct_var,
            "acc": acc,
            "month": month,
            "eom": eom_flag
        })
        conn.commit()
        st.success("Forecast submitted!")

# ---------- Load and Display Table ----------
with get_connection() as conn:
    df = pd.read_sql("SELECT * FROM revenue_forecast", conn)

df['Week'] = pd.to_datetime(df['Week'])

# Recalculate derived metrics (optional redundancy)
df['Flash vs Act'] = df['Flash Est'] - df['Actuals']
df['% Variance'] = df['Flash vs Act'] / df['Actuals']
df['Accuracy'] = (1 - abs(df['Flash vs Act']) / abs(df['Actuals'])).clip(lower=0)
df['Month'] = df['Week'].dt.month

# Update EOM field
df['EOM'] = ""
latest_weeks = df.groupby(['Region', 'Month'])['Week'].transform('max')
df.loc[df['Week'] == latest_weeks, 'EOM'] = 'EOM'

st.subheader("Forecast Table")
st.dataframe(df, use_container_width=True)

# ---------- Export Button ----------
st.download_button(
    label="Export to CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="revenue_forecast.csv",
    mime="text/csv"
)