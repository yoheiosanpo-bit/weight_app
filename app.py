import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import altair as alt  # ★追加：詳細なグラフ設定のためにインポート

# --- 設定 ---
SHEET_NAME = "体重管理"

# --- 認証と接続 ---
@st.cache_resource
def get_worksheet():
    credentials_dict = st.secrets["gcp_service_account"]
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        credentials_dict, scopes=scopes
    )
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

try:
    worksheet = get_worksheet()
except Exception as e:
    st.error(f"スプレッドシートへの接続に失敗しました: {e}")
    st.stop()

# --- アプリの画面 ---
st.title("記録アプリ")

# ==========================================
# 1. 全員のデータを表示（グラフの調整）
# ==========================================
st.header("みんなの体重推移")

all_records = worksheet.get_all_records()

if all_records:
    df = pd.DataFrame(all_records)
    
    if '名前' in df.columns:
        # 日付を変換
        df['日付'] = pd.to_datetime(df['日付'])
        
        # ★ここを変更：Altairを使って0から始まらないグラフを作成
        # Y軸の設定で scale=alt.Scale(zero=False) にするのがポイントです
        chart = alt.Chart(df).mark_line(point=True).encode(
            x=alt.X('日付', title='日付'),
            y=alt.Y('体重', title='体重 (kg)', scale=alt.Scale(zero=False)), 
            color='名前',
            tooltip=['日付', '名前', '体重'] # マウスを乗せると詳細を表示
        ).interactive() # 拡大縮小できるようにする

        # グラフを画面幅いっぱいに中央配置で表示
        st.altair_chart(chart, use_container_width=True)
        
        with st.expander("データ一覧を見る"):
            st.dataframe(df.sort_values('日付', ascending=False))
            
    else:
        st.error("エラー：スプレッドシートに「名前」列が見つかりません。")
else:
    st.info("データがまだありません。")

st.divider()

# ==========================================
# 2. 新しいデータを入力
# ==========================================
st.header("新しく記録する")

user_name = st.text_input("名前を入力してください", key="user_name")

if not user_name:
    st.info("記録するには名前を入力してください。")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    input_date = st.date_input('日付', datetime.today())
with col2:
    input_weight = st.number_input('体重 (kg)', min_value=0.0, step=0.1, format="%.1f")

if st.button("保存"):
    date_str = input_date.strftime('%Y-%m-%d')
    row_data = [date_str, input_weight, user_name]
    worksheet.append_row(row_data)
    
    st.success(f"{user_name} さんのデータを保存しました！")
    time.sleep(1)
    st.rerun()
