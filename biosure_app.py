import os
import subprocess
import sys
import time
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# ==========================================
# PART 1: GENERATE SYNTHETIC DATA
# ==========================================
print("1. Generating Synthetic Data...")

def generate_data():
    # --- A. CLAIMS DATA ---
    claims_data = []
    cart_drugs = [{'code': 'Q2041', 'desc': 'Yescarta', 'cost': 420000}]
    rescue_events = [
        {'code': 'J9359', 'desc': 'Glofitamab (Columvi)', 'type': 'Rescue'},
        {'code': 'Z51.5', 'desc': 'Hospice', 'type': 'Failure'}
    ]
    
    # --- B. PHARMA INTERNAL DATA ---
    pharma_data = []
    
    for i in range(100):
        patient_id = f"PT-{10000+i}"
        start_date = datetime(2023, 6, 1) + timedelta(days=random.randint(0, 365))
        revenue = 420000
        initial_reserve = revenue * 0.40 
        
        pharma_data.append({
            "Patient_ID": patient_id,
            "Shipment_Date": start_date.strftime("%Y-%m-%d"),
            "Payer": "Commercial Plan",
            "Revenue_Booked": revenue,
            "Current_Reserve_Held": initial_reserve,
            "Contract_Terms": "100% Rebate if Fail < 6mo"
        })

        claims_data.append({
            "Patient_ID": patient_id,
            "Date": start_date.strftime("%Y-%m-%d"),
            "Code": "Q2041",
            "Description": "CAR-T Infusion"
        })

        if random.random() < 0.30:
            fail_days = random.randint(30, 200)
            fail_date = start_date + timedelta(days=fail_days)
            rescue = random.choice(rescue_events)
            claims_data.append({
                "Patient_ID": patient_id,
                "Date": fail_date.strftime("%Y-%m-%d"),
                "Code": rescue['code'],
                "Description": rescue['desc']
            })

    pd.DataFrame(claims_data).to_csv("biosure_claims.csv", index=False)
    pd.DataFrame(pharma_data).to_csv("biosure_pharma.csv", index=False)
    print("✅ Data Generated.")

generate_data()

# ==========================================
# PART 2: DASHBOARD CODE
# ==========================================
print("2. Writing App Code...")

app_code = r"""
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os  # <--- FIXED: Added missing import
from datetime import datetime

st.set_page_config(page_title="BioSure | Liability Forecaster", layout="wide", page_icon="🧬")

st.markdown("""
<style>
    .metric-card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #a3e635;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-title { color: #94a3b8; font-size: 14px; font-weight: 500; }
    .metric-value { color: #ffffff; font-size: 28px; font-weight: 700; }
    .cash-release { border-left-color: #a3e635 !important; }
    .liability-hit { border-left-color: #ef4444 !important; }
</style>
""", unsafe_allow_html=True)

# --- LOGIC: CASH RELEASE ---
def analyze_portfolio(pharma_df, claims_df):
    pharma_df['Shipment_Date'] = pd.to_datetime(pharma_df['Shipment_Date'])
    claims_df['Date'] = pd.to_datetime(claims_df['Date'])
    merged = pd.merge(pharma_df, claims_df, on="Patient_ID", how="left", suffixes=('_Int', '_Ext'))
    merged['BioSure_Status'] = 'Active'
    merged['Cash_Impact'] = 0.0
    
    patient_groups = merged.groupby('Patient_ID')
    results = []
    
    for pid, group in patient_groups:
        info = group.iloc[0]
        ship_date = info['Shipment_Date']
        reserve = info['Current_Reserve_Held']
        booked = info['Revenue_Booked']
        rescue_codes = ['J9359', 'Z51.5']
        failures = group[group['Code'].isin(rescue_codes)]
        current_date = datetime(2024, 10, 1)
        days_since = (current_date - ship_date).days
        
        record = {'Patient_ID': pid, 'Days_On_Therapy': days_since, 'Current_Reserve': reserve, 'Status': 'Monitoring', 'Cash_Impact': 0.0}

        if not failures.empty:
            fail_date = failures.iloc[0]['Date']
            days_to_fail = (fail_date - ship_date).days
            rebate_owed = booked if days_to_fail < 180 else 0
            record['Status'] = 'Failure Confirmed'
            record['Cash_Impact'] = -(rebate_owed - reserve)
        else:
            if days_since > 180:
                record['Status'] = 'Safe (Risk Expired)'
                record['Cash_Impact'] = reserve
            elif days_since > 90:
                record['Status'] = 'Low Risk (Partial Release)'
                record['Cash_Impact'] = reserve * 0.5
        
        results.append(record)
    return pd.DataFrame(results)

# --- LOGIC: RISK SIMULATION ---
def simulate_forecast_evolution():
    data = [
        {"Quarter": "Q1 (Launch)", "Reserve_Rate": 0.40, "Lower_Bound": 0.25, "Upper_Bound": 0.55, "Type": "Manual Guess"},
        {"Quarter": "Q2 (BioSure)", "Reserve_Rate": 0.36, "Lower_Bound": 0.30, "Upper_Bound": 0.42, "Type": "AI Calibrated"},
        {"Quarter": "Q3 (BioSure)", "Reserve_Rate": 0.34, "Lower_Bound": 0.31, "Upper_Bound": 0.37, "Type": "AI Calibrated"},
        {"Quarter": "Q4 (Actuals)", "Reserve_Rate": 0.32, "Lower_Bound": 0.31, "Upper_Bound": 0.33, "Type": "True Reality"}
    ]
    return pd.DataFrame(data)

def main():
    st.sidebar.title("🧬 BioSure")
    
    if os.path.exists("biosure_pharma.csv"):
        pharma_df = pd.read_csv("biosure_pharma.csv")
        claims_df = pd.read_csv("biosure_claims.csv")
    else:
        st.error("Data missing.")
        st.stop()

    tab1, tab2 = st.tabs(["💰 Cash Release (Current)", "📉 Risk Reduction (Future)"])

    # --- TAB 1: CURRENT STATE ---
    with tab1:
        st.title("Net Asset Value (NAV) Adjuster")
        ledger = analyze_portfolio(pharma_df, claims_df)
        
        cash_unlock = ledger[ledger['Cash_Impact'] > 0]['Cash_Impact'].sum()
        new_liability = ledger[ledger['Cash_Impact'] < 0]['Cash_Impact'].sum()
        net_benefit = cash_unlock + new_liability

        m1, m2, m3, m4 = st.columns(4)
        with m1: st.markdown(f'<div class="metric-card"><div class="metric-title">Total Reserves</div><div class="metric-value">${ledger["Current_Reserve"].sum()/1000000:.1f}M</div></div>', unsafe_allow_html=True)
        with m2: st.markdown(f'<div class="metric-card cash-release"><div class="metric-title">Cash Unlock</div><div class="metric-value">+${cash_unlock/1000000:.1f}M</div></div>', unsafe_allow_html=True)
        with m3: st.markdown(f'<div class="metric-card liability-hit"><div class="metric-title">New Liability</div><div class="metric-value">-${abs(new_liability)/1000000:.1f}M</div></div>', unsafe_allow_html=True)
        with m4: 
            color = "#a3e635" if net_benefit > 0 else "#ef4444"
            st.markdown(f'<div class="metric-card" style="border-left-color: {color};"><div class="metric-title">Net Benefit</div><div class="metric-value">${net_benefit/1000000:.1f}M</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Adjusted Ledger")
        st.dataframe(ledger.sort_values('Cash_Impact', ascending=False), use_container_width=True)

    # --- TAB 2: FUTURE STATE ---
    with tab2:
        st.title("Forecast Precision Evolution")
        st.markdown("**The BioSure Effect:** Moving from conservative guesses to precision reserves.")
        
        sim_data = simulate_forecast_evolution()
        
        base = alt.Chart(sim_data).encode(x=alt.X('Quarter', sort=None))

        area = base.mark_area(opacity=0.3, color='#3b82f6').encode(
            y='Lower_Bound',
            y2='Upper_Bound'
        )
        
        line = base.mark_line(color='#a3e635', strokeWidth=4).encode(
            y='Reserve_Rate'
        )
        
        points = base.mark_circle(size=100, color='white').encode(
            y='Reserve_Rate',
            tooltip=['Quarter', 'Reserve_Rate', 'Type']
        )

        chart = (area + line + points).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
        
        col_a, col_b = st.columns([1,1])
        with col_a:
            st.info("### Q1: The Manual Guess\\nCFO books **40%** reserve to be safe. \\n**Result:** Millions in trapped capital.")
        with col_b:
            st.success("### Q4: The BioSure Reality\\nAI proves actual failure rate is **32%**. \\n**Result:** Permanent release of 8% revenue margin.")

if __name__ == "__main__":
    main()
"""

with open("biosure_app.py", "w") as f:
    f.write(app_code)

# ==========================================
# PART 3: LAUNCH
# ==========================================
print("3. Launching...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "streamlit", "altair", "pandas", "numpy"])

if not os.path.exists("cloudflared-linux-amd64"):
    subprocess.run(["wget", "-q", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"], check=True)
    subprocess.run(["chmod", "+x", "cloudflared-linux-amd64"], check=True)

subprocess.Popen(["streamlit", "run", "biosure_app.py", "--server.headless", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

time.sleep(3)
tunnel_cmd = "./cloudflared-linux-amd64 tunnel --url http://localhost:8501"
tunnel_process = subprocess.Popen(tunnel_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

print("Searching for link...")
try:
    for line in iter(tunnel_process.stderr.readline, ''):
        if "trycloudflare.com" in line:
            import re
            url_match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if url_match:
                print(f"✅ DASHBOARD READY! Click: {url_match.group(0)}")
                break
except KeyboardInterrupt:
    tunnel_process.kill()