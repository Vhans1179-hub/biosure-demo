import os
import subprocess
import sys
import time
import urllib.request

# --- PART 1: THE APP CODE (Embedded) ---
# This saves the Streamlit app to a file on the Colab machine
app_code = """
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta

# Page Config
st.set_page_config(page_title="BioSure | Liability Forecaster", layout="wide", page_icon="🧬")

# CSS Styling
st.markdown(\"\"\"
<style>
    .metric-card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #a3e635;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-title {
        color: #94a3b8;
        font-size: 14px;
        font-weight: 500;
    }
    .metric-value {
        color: #ffffff;
        font-size: 28px;
        font-weight: 700;
    }
</style>
\"\"\", unsafe_allow_html=True)

# Mock Data Generator
def generate_mock_data(n_patients=50):
    patients = []
    rescue_drugs = ['Glofitamab', 'Epcoritamab', 'Talquetamab', 'Stem Cell Transplant', 'Hospice']
    
    for i in range(n_patients):
        pid = f"PT-{1000+i}"
        infusion_date = datetime(2024, 1, 1) + timedelta(days=np.random.randint(0, 180))
        
        # Simulate 30% Failure Rate
        if np.random.random() < 0.30:
            status = "Failure Detected"
            days_to_fail = np.random.randint(30, 200)
            event_date = infusion_date + timedelta(days=days_to_fail)
            trigger = np.random.choice(rescue_drugs)
        else:
            status = "Active / Remission"
            days_to_fail = None
            event_date = datetime.now()
            trigger = None
            
        patients.append({
            "Patient ID": pid,
            "Infusion Date": infusion_date,
            "Last Signal Date": event_date,
            "Status": status,
            "Failure Trigger": trigger,
            "Days Post Infusion": (event_date - infusion_date).days if status == "Failure Detected" else (datetime.now() - infusion_date).days
        })
    return pd.DataFrame(patients)

# Logic Engine
def calculate_liability(df):
    liabilities = []
    for index, row in df.iterrows():
        liability = 0
        if row["Status"] == "Failure Detected":
            days = row["Days Post Infusion"]
            # Contract Terms
            if days <= 90:
                liability = 400000
            elif days <= 180:
                liability = 300000
            elif days <= 365:
                liability = 200000
        liabilities.append(liability)
    df["projected_rebate"] = liabilities
    return df

# Main UI
def main():
    st.sidebar.title("🧬 BioSure")
    st.sidebar.markdown("### Financial Clearinghouse")
    contract_select = st.sidebar.selectbox("Select Therapy Contract", ["Yescarta (Gilead)", "Kymriah (Novartis)", "Carvykti (Janssen)"])
    st.sidebar.divider()
    st.sidebar.info(f"Monitoring **{contract_select}** Outcome-Based Contract (OBC).")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("Liability Forecast Dashboard")
        st.markdown(f"**Entity:** Global Pharma Corp | **Product:** {contract_select}")
    with col2:
        if st.button("🔄 Ingest Latest Claims"):
            st.toast("Connecting to ConcertAI... Data Refreshed!", icon="✅")

    raw_data = generate_mock_data(100)
    processed_data = calculate_liability(raw_data)
    
    total_revenue = len(processed_data) * 400000 
    total_liability = processed_data["projected_rebate"].sum()
    net_revenue = total_revenue - total_liability
    fail_count = len(processed_data[processed_data["Status"] == "Failure Detected"])
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Total Contract Revenue</div><div class="metric-value">${total_revenue/1000000:.1f}M</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card" style="border-left-color: #ef4444;"><div class="metric-title">Projected Liability</div><div class="metric-value">${total_liability/1000000:.2f}M</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card" style="border-left-color: #3b82f6;"><div class="metric-title">Net Revenue</div><div class="metric-value">${net_revenue/1000000:.1f}M</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card" style="border-left-color: #f59e0b;"><div class="metric-title">Failure Signals</div><div class="metric-value">{fail_count}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Liability by Trigger Event")
        failures = processed_data[processed_data["projected_rebate"] > 0]
        chart = alt.Chart(failures).mark_bar().encode(
            x=alt.X('Failure Trigger', sort='-y'),
            y='sum(projected_rebate)',
            color=alt.Color('Failure Trigger', scale=alt.Scale(scheme='reds'))
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
        
    with c2:
        st.subheader("Status Distribution")
        pie = alt.Chart(processed_data).mark_arc(innerRadius=50).encode(
            theta=alt.Theta("count()", stack=True),
            color=alt.Color("Status", scale=alt.Scale(domain=['Active / Remission', 'Failure Detected'], range=['#a3e635', '#ef4444']))
        )
        st.altair_chart(pie, use_container_width=True)

    st.subheader("Adjudication Ledger (Live Stream)")
    display_df = processed_data.copy()
    display_df["Revenue Impact"] = display_df["projected_rebate"].apply(lambda x: f"-${x:,.0f}" if x > 0 else "$0")
    display_df["Infusion Date"] = display_df["Infusion Date"].dt.date
    st.dataframe(display_df[["Patient ID", "Infusion Date", "Status", "Failure Trigger", "Days Post Infusion", "Revenue Impact"]].sort_values(by="Revenue Impact", ascending=True), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
"""

# --- PART 2: CLOUDFLARE LAUNCHER ---

print("1. Saving Application Code...")
with open("biosure_app.py", "w") as f:
    f.write(app_code)

print("2. Installing Dependencies (Streamlit, Altair)...")
# We use subprocess to run pip install quietly
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "streamlit", "altair", "pandas", "numpy"])

print("3. Installing Cloudflare Tunnel...")
# Download cloudflared if not present
if not os.path.exists("cloudflared-linux-amd64"):
    subprocess.run(["wget", "-q", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"], check=True)
    subprocess.run(["chmod", "+x", "cloudflared-linux-amd64"], check=True)

print("4. Starting Dashboard Server...")
# Start Streamlit in the background on port 8501
subprocess.Popen(["streamlit", "run", "biosure_app.py", "--server.headless", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("5. Establishing Tunnel...")
# Start Cloudflare tunnel pointing to localhost:8501
time.sleep(3) # Wait for Streamlit to spin up
tunnel_cmd = "./cloudflared-linux-amd64 tunnel --url http://localhost:8501"
tunnel_process = subprocess.Popen(tunnel_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

print("\n" + "="*60)
print("  SEARCHING FOR LINK (Please wait 10-15 seconds)...")
print("="*60 + "\n")

# Read the tunnel output to find the unique URL
try:
    for line in iter(tunnel_process.stderr.readline, ''):
        if "trycloudflare.com" in line:
            import re
            url_match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if url_match:
                url = url_match.group(0)
                print(f"✅ SUCCESS! Click to view your Dashboard: {url}")
                print("\n(Keep this cell running to keep the app online)")
                break
except KeyboardInterrupt:
    print("Stopping...")
    tunnel_process.kill()