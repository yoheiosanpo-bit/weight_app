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
st.title("記録アプリ")

# 1. 入力エリア

# --- 名前入力 ---
user_name = st.text_input("名前を入力してください", key="user_name")

if not user_name:
    st.warning("記録するには名前を入力してください。")
    st.stop() # 名前がない場合はここで処理を止める

st.header('今日の記録')
col1, col2 = st.columns(2)
with col1:
    input_date = st.date_input('日付', datetime.today())
with col2:
    input_weight = st.number_input('体重 (kg)', min_value=0.0, step=0.1, format="%.1f")

if st.button("保存"):
    # 日付を文字列に変換
    date_str = input_date.strftime('%Y-%m-%d')
    
    # 保存するデータの作成（スプレッドシートの列の並び順：A=日付, B=体重, C=名前）
    # リスト形式で作成します
    row_data = [date_str, input_weight, user_name]
    
    # スプレッドシートに行を追加
    worksheet.append_row(row_data)
    
    st.success(f"{user_name} さんのデータを保存しました！")
    
    # 少し待ってからリロード（データ反映のため）
    import time
    time.sleep(1)
    st.rerun()

# 2. データ表示エリア
st.divider()
st.header(f'{user_name} さんの体重推移')

# 全データを取得
all_records = worksheet.get_all_records()

if all_records:
    df = pd.DataFrame(all_records)
    
    # --- 重要：名前でデータを絞り込む ---
    # 「名前」列が、入力された user_name と一致する行だけ抜き出す
    # ※スプレッドシートに「名前」というヘッダーが必要です
    if '名前' in df.columns:
        df_filtered = df[df['名前'] == user_name]
    else:
        st.error("エラー：スプレッドシートに「名前」列がありません。1行目C列に「名前」を追加してください。")
        st.stop()
    
    if not df_filtered.empty:
        # 日付列を日付型に変換（グラフ用）
        df_filtered['日付'] = pd.to_datetime(df_filtered['日付'])
        
        # グラフ描画
        st.line_chart(df_filtered, x='日付', y='体重')
        
        # 最新5件を表示
        st.subheader('最近の履歴')
        st.dataframe(df_filtered.sort_values('日付', ascending=False).head(5))
    else:
        st.info(f'{user_name} さんのデータはまだありません。保存ボタンから登録してください。')
else:
    st.info('データがまだありません。')
