import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 設定 ---
# スプレッドシートの名前（ステップ2でつけた名前と完全に一致させてください）
SHEET_NAME = "体重管理"

# --- 認証と接続（キャッシュを使って高速化） ---
@st.cache_resource
def get_worksheet():
    # Secretsから鍵情報を取得
    credentials_dict = st.secrets["gcp_service_account"]
    
    # 認証スコープの設定
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 認証を行う
    creds = Credentials.from_service_account_info(
        credentials_dict, scopes=scopes
    )
    client = gspread.authorize(creds)
    
    # シートを開く
    return client.open(SHEET_NAME).sheet1

try:
    worksheet = get_worksheet()
except Exception as e:
    st.error(f"スプレッドシートへの接続に失敗しました: {e}")
    st.stop()

# --- アプリの画面 ---
st.title('☁️ クラウド体重記録アプリ')

# 1. 入力エリア
st.header('今日の記録')
col1, col2 = st.columns(2)
with col1:
    input_date = st.date_input('日付', datetime.today())
with col2:
    input_weight = st.number_input('体重 (kg)', min_value=0.0, step=0.1, format="%.1f")

if st.button('記録を保存'):
    # 日付を文字列に変換
    date_str = input_date.strftime('%Y-%m-%d')
    # スプレッドシートに行を追加（append_row）
    worksheet.append_row([date_str, input_weight])
    st.success('Googleスプレッドシートに保存しました！')
    
    # データを再読み込みするためにリロードを促す（または自動でクリア）
    st.rerun()

# 2. データ表示エリア
st.divider()
st.header('体重の推移')

# 全データを取得
all_records = worksheet.get_all_records()

if all_records:
    df = pd.DataFrame(all_records)
    
    # 日付列を日付型に変換（グラフ用）
    df['日付'] = pd.to_datetime(df['日付'])
    
    # グラフ描画
    st.line_chart(df, x='日付', y='体重')
    
    # 最新5件を表示
    st.subheader('最近の履歴')
    st.dataframe(df.sort_values('日付', ascending=False).head(5))
else:
    st.info('データがまだありません。')