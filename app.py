import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- 設定 ---
SHEET_NAME = "体重管理"

# --- 認証と接続 ---
@st.cache_resource
def get_worksheet():
    # Secretsから鍵情報を取得
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
# 1. 全員のデータを表示（画面の一番上）
# ==========================================
st.header("みんなの体重推移")

# 全データを取得
all_records = worksheet.get_all_records()

if all_records:
    df = pd.DataFrame(all_records)
    
    # スプレッドシートに「名前」列があるか確認
    if '名前' in df.columns:
        # 日付を変換
        df['日付'] = pd.to_datetime(df['日付'])
        
        # ★ここがポイント：color='名前' で人ごとに色分け
        st.line_chart(df, x='日付', y='体重', color='名前')
        
        # データ一覧も表示（新しい順）
        with st.expander("データ一覧を見る"):
            st.dataframe(df.sort_values('日付', ascending=False))
            
    else:
        st.error("エラー：スプレッドシートに「名前」列が見つかりません。")
else:
    st.info("データがまだありません。")

st.divider() # 区切り線

# ==========================================
# 2. 新しいデータを入力
# ==========================================
st.header("新しく記録する")

user_name = st.text_input("名前を入力してください", key="user_name")

# 名前が入力されていないときは、ここで入力を促して止める（グラフは上で表示済み）
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
    
    # 保存データ（A列:日付, B列:体重, C列:名前）
    row_data = [date_str, input_weight, user_name]
    
    worksheet.append_row(row_data)
    
    st.success(f"{user_name} さんのデータを保存しました！")
    
    # 自動リロード
    time.sleep(1)
    st.rerun()
