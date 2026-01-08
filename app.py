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

# タイトル
st.markdown("""
    <h1 style='font-size: 22px; white-space: nowrap; margin-bottom: 20px;'>
        うによ-¯•ω•¯-ほこ減量！？チャンネル
    </h1>
""", unsafe_allow_html=True)

# データを取得
all_records = worksheet.get_all_records()
df = pd.DataFrame(all_records) if all_records else pd.DataFrame()

# ==========================================
# 1. 全員のデータを表示（グラフ＆表）
# ==========================================
st.header("みんなの体重推移")

if not df.empty and '名前' in df.columns:
    df['日付'] = pd.to_datetime(df['日付'])

    # --- 期間選択フィルタ（ボタンのみ） ---
    period_option = st.radio(
        label="期間選択",
        options=["全期間", "7日", "1か月", "3か月", "1年"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

    # フィルタリング処理
    filtered_df = df.copy()
    today = pd.Timestamp.now().normalize()

    if period_option == "7日":
        start_date = today - pd.Timedelta(days=7)
        filtered_df = filtered_df[filtered_df['日付'] >= start_date]
    elif period_option == "1か月":
        start_date = today - pd.DateOffset(months=1)
        filtered_df = filtered_df[filtered_df['日付'] >= start_date]
    elif period_option == "3か月":
        start_date = today - pd.DateOffset(months=3)
        filtered_df = filtered_df[filtered_df['日付'] >= start_date]
    elif period_option == "1年":
        start_date = today - pd.DateOffset(years=1)
        filtered_df = filtered_df[filtered_df['日付'] >= start_date]
    
    # グラフ描画
    if not filtered_df.empty:
        # データの最小日と最大日を取得
        min_date = filtered_df['日付'].min()
        max_date = filtered_df['日付'].max()

        # ★修正：どの期間が選ばれていても、データ期間の15%を余白にする
        duration_days = (max_date - min_date).days
        
        # 期間が極端に短い（0日など）場合に備えて最低1日を確保
        if duration_days <= 0:
             buffer_days = 1
        else:
             buffer_days = int(duration_days * 0.15)
             # 計算結果が0日になる場合（例:データが2日分しかない等）も最低1日は確保
             if buffer_days < 1:
                 buffer_days = 1
        
        # 計算した日数分だけ未来の日付を追加
        future_buffer = max_date + pd.Timedelta(days=buffer_days)
        
        # X軸のドメイン（範囲）リストを作成
        domain_range = [min_date, future_buffer]

        chart = alt.Chart(filtered_df).mark_line(point=True).encode(
            x=alt.X('日付', title=None, 
                    axis=alt.Axis(format='%Y/%m/%d', labelAngle=-45),
                    scale=alt.Scale(domain=domain_range)
            ),
            y=alt.Y('体重', title='体重 (kg)', scale=alt.Scale(zero=False)), 
            color='名前',
            tooltip=[alt.Tooltip('日付', title='日付', format='%Y/%m/%d'), '名前', '体重']
        ).interactive().configure_axis(
            labelFontSize=12,
            titleFontSize=14
        ).configure_legend(
            orient='bottom',      
            direction='horizontal', 
            titleFontSize=14,
            labelFontSize=12,
            title=None            
        )

        st.altair_chart(chart, use_container_width=True)
        
        # 履歴一覧表
        with st.expander("履歴一覧表を見る"):
            display_df = filtered_df.copy()
            display_df['日付'] = display_df['日付'].dt.strftime('%Y/%m/%d')
            st.dataframe(display_df.sort_values('日付', ascending=False), use_container_width=True)
    else:
        st.info(f"過去 {period_option} のデータはありません。")

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
    new_name_input = st.text_input("新しい名前を入力", key="new_name_input")

    if 'confirm_merge' not in st.session_state:
        st.session_state.confirm_merge = False
    if 'target_name' not in st.session_state:
        st.session_state.target_name = ""

    def execute_name_change(current_name, target_name):
        try:
            cells_to_update = []
            all_values = worksheet.get_all_values()
            
            header = all_values[0]
            try:
                name_col_index = header.index("名前")
            except ValueError:
                st.error("スプレッドシートに「名前」列が見つかりません。")
                return

            count = 0
            for i, row in enumerate(all_values):
                if i == 0: continue
                if len(row) > name_col_index and row[name_col_index] == current_name:
                    cells_to_update.append(
                        Cell(row=i+1, col=name_col_index+1, value=target_name)
                    )
                    count += 1
            
            if cells_to_update:
                worksheet.update_cells(cells_to_update)
                st.success(f"{count} 件のデータを「{current_name}」から「{target_name}」に変更しました！")
                st.session_state.confirm_merge = False
                time.sleep(2)
                st.rerun()
            else:
                st.warning(f"「{current_name}」のデータが見つかりませんでした。")
                
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

    if st.button("名前変更を確認"):
        if not new_name_input:
             st.warning("新しい名前を入力してください。")
        elif new_name_input == user_name:
             st.warning("新しい名前が現在の名前と同じです。")
        else:
            existing_names = []
            if not df.empty and '名前' in df.columns:
                existing_names = df['名前'].unique().tolist()
            
            if new_name_input in existing_names:
                st.session_state.confirm_merge = True
                st.session_state.target_name = new_name_input
            else:
                execute_name_change(user_name, new_name_input)

    if st.session_state.confirm_merge:
        st.warning(
            f"⚠️ 名前「{st.session_state.target_name}」は既に存在します。\n\n"
            f"実行すると「{user_name}」のデータが「{st.session_state.target_name}」に統合されます。"
        )
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("統合して変更する", type="primary"):
                execute_name_change(user_name, st.session_state.target_name)
        with col_m2:
            if st.button("キャンセルして戻る"):
                st.session_state.confirm_merge = False
                st.rerun()

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
