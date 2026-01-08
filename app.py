import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import altair as alt

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

# データを取得（ここで一度だけ取得して使い回します）
all_records = worksheet.get_all_records()
df = pd.DataFrame(all_records) if all_records else pd.DataFrame()

# ==========================================
# 1. 全員のデータを表示（グラフ）
# ==========================================
st.header("みんなの体重推移")

if not df.empty and '名前' in df.columns:
    # 日付を変換
    df['日付'] = pd.to_datetime(df['日付'])
    
    # グラフ作成
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X('日付', title='日付'),
        y=alt.Y('体重', title='体重 (kg)', scale=alt.Scale(zero=False)), 
        color='名前',
        tooltip=['日付', '名前', '体重']
    ).interactive()

    st.altair_chart(chart, use_container_width=True)
else:
    if df.empty:
        st.info("データがまだありません。")
    else:
        st.error("エラー：スプレッドシートに「名前」列がありません。")

st.divider()

# ==========================================
# 2. 新しいデータを入力
# ==========================================
st.header("新しく記録する")

user_name = st.text_input("名前を入力してください", key="user_name")

if not user_name:
    st.info("記録、または削除するには名前を入力してください。")
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

# ==========================================
# 3. データの削除機能（★追加部分）
# ==========================================
st.divider()
st.subheader("データの削除")

# 自分のデータだけを抽出
if not df.empty and '名前' in df.columns:
    # データフレームの日付を文字列に戻して比較用にする
    df['日付_str'] = df['日付'].dt.strftime('%Y-%m-%d')
    my_df = df[df['名前'] == user_name].sort_values('日付', ascending=False)
    
    if not my_df.empty:
        with st.expander("データを削除する"):
            st.write("削除したいデータの日付を選んでください。")
            
            # 日付と体重を表示して選ばせる
            # 例: "2024-01-01 (60.5kg)" のように表示
            date_options = my_df['日付_str'].tolist()
            selected_date = st.selectbox("日付を選択", date_options)
            
            # 選んだ日付の体重を取得（確認用）
            target_row = my_df[my_df['日付_str'] == selected_date].iloc[0]
            st.warning(f"警告：本当に {selected_date} の記録（{target_row['体重']}kg）を削除しますか？")
            
            if st.button("削除実行", type="primary"):
                try:
                    # スプレッドシート上の行を探す処理
                    # 全データをリストで取得（ヘッダー含む）
                    all_values = worksheet.get_all_values()
                    
                    row_to_delete = None
                    
                    # 1行目(index 0)はヘッダーなので、1からスタート
                    for i, row in enumerate(all_values):
                        if i == 0: continue
                        
                        # row[0]=日付, row[2]=名前 と想定
                        # スプレッドシートの日付形式と一致させる必要があります
                        if row[0] == selected_date and row[2] == user_name:
                            row_to_delete = i + 1 # スプレッドシートは1始まりのため
                            break
                    
                    if row_to_delete:
                        worksheet.delete_rows(row_to_delete)
                        st.success("削除しました。")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("削除対象の行が見つかりませんでした。")
                        
                except Exception as e:
                    st.error(f"削除中にエラーが発生しました: {e}")
    else:
        st.info(f"{user_name} さんの削除可能なデータはありません。")
