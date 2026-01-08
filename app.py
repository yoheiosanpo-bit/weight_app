import streamlit as st
import pandas as pd
import gspread
from gspread import Cell
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
st.title("うによ-¯•ω•¯-ほこ減量！？チャンネル")

# データを取得
all_records = worksheet.get_all_records()
df = pd.DataFrame(all_records) if all_records else pd.DataFrame()

# ==========================================
# 1. 全員のデータを表示（グラフ）
# ==========================================
st.header("みんなの体重推移")

if not df.empty and '名前' in df.columns:
    df['日付'] = pd.to_datetime(df['日付'])
    
    # ★ここを修正：日付フォーマットと文字サイズの調整
    chart = alt.Chart(df).mark_line(point=True).encode(
        # axis=alt.Axis(format='%m/%d') で「12/01」のような形式に指定
        x=alt.X('日付', title='日付', axis=alt.Axis(format='%m/%d', labelAngle=0)),
        y=alt.Y('体重', title='体重 (kg)', scale=alt.Scale(zero=False)), 
        color='名前',
        # マウスを乗せたときの表示も「12/01」形式にする
        tooltip=[alt.Tooltip('日付', title='日付', format='%m/%d'), '名前', '体重']
    ).interactive().configure_axis(
        # PCで見やすいように文字サイズを大きくする設定
        labelFontSize=12,
        titleFontSize=14
    ).configure_legend(
        # 凡例（名前リスト）の文字サイズも調整
        titleFontSize=14,
        labelFontSize=12
    )

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
    st.info("記録、または管理機能を使うには名前を入力してください。")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    input_date = st.date_input('日付', datetime.today())
with col2:
    input_weight = st.number_input('体重 (kg)', min_value=0.0, step=0.1, format="%.1f")

if st.button("保存"):
    date_str = input_date.strftime('%Y-%m-%d')
    # 名前はC列（3列目）を想定
    row_data = [date_str, input_weight, user_name]
    
    worksheet.append_row(row_data)
    st.success(f"{user_name} さんのデータを保存しました！")
    time.sleep(1)
    st.rerun()

st.divider()

# ==========================================
# 3. データの管理（削除・名前変更）
# ==========================================
st.header("データの管理")

# --- 名前変更機能 ---
with st.expander("登録名を変更する"):
    st.write(f"現在の名前「**{user_name}**」のデータをすべて、新しい名前に書き換えます。")
    new_name = st.text_input("新しい名前を入力", key="new_name_input")
    
    if st.button("名前を変更する"):
        if new_name and new_name != user_name:
            try:
                # 変更対象のセルリストを作成
                cells_to_update = []
                all_values = worksheet.get_all_values()
                header = all_values[0]
                try:
                    name_col_index = header.index("名前")
                except ValueError:
                    st.error("スプレッドシートに「名前」列が見つかりません。")
                    st.stop()

                count = 0
                for i, row in enumerate(all_values):
                    if i == 0: continue
                    if len(row) > name_col_index and row[name_col_index] == user_name:
                        cells_to_update.append(
                            Cell(row=i+1, col=name_col_index+1, value=new_name)
                        )
                        count += 1
                
                if cells_to_update:
                    worksheet.update_cells(cells_to_update)
                    st.success(f"{count} 件のデータを「{new_name}」に変更しました！")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.warning(f"「{user_name}」のデータが見つかりませんでした。")
                    
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
        elif new_name == user_name:
            st.warning("新しい名前が現在の名前と同じです。")
        else:
            st.warning("新しい名前を入力してください。")

# --- データ削除機能 ---
with st.expander("データを削除する"):
    if not df.empty and '名前' in df.columns:
        df['日付_str'] = df['日付'].dt.strftime('%Y-%m-%d')
        my_df = df[df['名前'] == user_name].sort_values('日付', ascending=False)
        
        if not my_df.empty:
            st.write("削除したいデータの日付を選んでください。")
            date_options = my_df['日付_str'].tolist()
            selected_date = st.selectbox("日付を選択", date_options, key="delete_date")
            
            target_row_data = my_df[my_df['日付_str'] == selected_date].iloc[0]
            st.warning(f"警告：{selected_date} の記録（{target_row_data['体重']}kg）を削除しますか？")
            
            if st.button("削除実行", type="primary"):
                try:
                    all_values = worksheet.get_all_values()
                    row_to_delete = None
                    header = all_values[0]
                    name_idx = header.index("名前")
                    date_idx = header.index("日付")

                    for i, row in enumerate(all_values):
                        if i == 0: continue
                        if row[date_idx] == selected_date and row[name_idx] == user_name:
                            row_to_delete = i + 1
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
            st.info("削除可能なデータがありません。")
    else:
        st.info("データがありません。")
