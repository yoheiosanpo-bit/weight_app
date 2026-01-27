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

# --- ヘッダー確認と「身長」列の自動追加 ---
try:
    header_values = worksheet.row_values(1)
    if "身長" not in header_values:
        next_col = len(header_values) + 1
        worksheet.update_cell(1, next_col, "身長")
except Exception:
    pass

# --- アプリの画面 ---

st.markdown("""
    <h1 style='font-size: 22px; white-space: nowrap; margin-bottom: 20px;'>
        うによ-¯•ω•¯-ほこ減量！？チャンネル
    </h1>
""", unsafe_allow_html=True)

# データを取得
all_records = worksheet.get_all_records()
df = pd.DataFrame(all_records) if all_records else pd.DataFrame()

# ==========================================
# 1. データ加工（BMI計算）
# ==========================================
if not df.empty and '名前' in df.columns:
    df['日付'] = pd.to_datetime(df['日付'])
    df['体重'] = pd.to_numeric(df['体重'], errors='coerce')

    if '身長' not in df.columns:
        df['身長'] = None
    df['身長'] = pd.to_numeric(df['身長'], errors='coerce')

    df = df.sort_values('日付')

    # 表示・計算用の穴埋め（過去・未来へ伝播）
    df['身長_filled'] = df.groupby('名前')['身長'].ffill().bfill()

    # BMI計算
    df['BMI'] = df['体重'] / ((df['身長_filled'] / 100) ** 2)

# ==========================================
# 2. グラフ表示
# ==========================================
st.header("みんなの推移")

if not df.empty and '名前' in df.columns:
    period_option = st.radio(
        label="期間選択",
        options=["全期間", "7日", "1か月", "3か月", "1年"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

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
    
    if not filtered_df.empty:
        # X軸設定
        min_date = filtered_df['日付'].min()
        max_date = filtered_df['日付'].max()
        duration_days = (max_date - min_date).days

        if period_option == "7日": buffer_days = 1
        elif period_option == "1か月": buffer_days = 5
        elif period_option == "3か月": buffer_days = 15
        elif period_option == "1年": buffer_days = 60
        else:
             buffer_days = int(duration_days * 0.15) if duration_days > 0 else 1
             if buffer_days < 1: buffer_days = 1
        
        future_buffer = max_date + pd.Timedelta(days=buffer_days)
        domain_range = [min_date, future_buffer]

        # ① 体重グラフ
        st.subheader("体重 (kg)")
        weight_plot_df = filtered_df.dropna(subset=['体重'])
        if not weight_plot_df.empty:
            chart_weight = alt.Chart(weight_plot_df).mark_line(point=True).encode(
                x=alt.X('日付', title=None, 
                        axis=alt.Axis(format='%Y/%m/%d', labelAngle=-45),
                        scale=alt.Scale(domain=domain_range)
                ),
                y=alt.Y('体重', title='体重 (kg)', scale=alt.Scale(zero=False)), 
                color='名前',
                tooltip=[alt.Tooltip('日付', format='%Y/%m/%d'), '名前', '体重']
            ).interactive().configure_axis(
                labelFontSize=12, titleFontSize=14
            ).configure_legend(
                orient='bottom', direction='horizontal', title=None
            )
            st.altair_chart(chart_weight, use_container_width=True)
        else:
            st.info("表示期間内に体重データがありません。")

        # ② BMIグラフ（背景色付き）
        st.subheader("BMI")
        bmi_df = filtered_df.dropna(subset=['BMI'])
        
        if not bmi_df.empty:
            line = alt.Chart(bmi_df).mark_line(point=True).encode(
                x=alt.X('日付', title=None, 
                        axis=alt.Axis(format='%Y/%m/%d', labelAngle=-45),
                        scale=alt.Scale(domain=domain_range)
                ),
                y=alt.Y('BMI', title='BMI', scale=alt.Scale(zero=False)), 
                color='名前',
                tooltip=[
                    alt.Tooltip('日付', format='%Y/%m/%d'), 
                    '名前', 
                    alt.Tooltip('BMI', format='.1f'),
                    alt.Tooltip('身長_filled', title='身長', format='.1f')
                ]
            )

            # 普通体重ゾーン(18.5〜25)
            band_data = pd.DataFrame({
                'start': [min_date], 'end': [future_buffer],
                'y1': [18.5], 'y2': [25.0]
            })

            band = alt.Chart(band_data).mark_rect(color='#66BB6A', opacity=0.15).encode(
                x='start', x2='end', y='y1', y2='y2'
            )
            
            st.caption("🟩 緑色の帯は「普通体重（BMI 18.5〜25.0）」の範囲です。")

            chart_bmi = alt.layer(band, line).interactive().configure_axis(
                labelFontSize=12, titleFontSize=14
            ).configure_legend(
                orient='bottom', direction='horizontal', title=None
            )
            st.altair_chart(chart_bmi, use_container_width=True)
        else:
            st.info("身長・体重データが揃っていないため、BMIを表示できません。")

        # 履歴一覧表
        with st.expander("履歴一覧表を見る"):
            display_df = filtered_df.copy()
            display_df['日付'] = display_df['日付'].dt.strftime('%Y/%m/%d')
            cols = ['日付', '名前']
            if '体重' in display_df.columns: cols.append('体重')
            if '身長' in display_df.columns: cols.append('身長')
            if 'BMI' in display_df.columns: cols.append('BMI')
            
            st.dataframe(display_df[cols].sort_values('日付', ascending=False), use_container_width=True)

    else:
        st.info(f"過去 {period_option} のデータはありません。")
else:
    if df.empty:
        st.info("データがまだありません。")
    else:
        st.error("エラー：データ形式が正しくありません。")

st.divider()

# ==========================================
# 3. 新しいデータを入力
# ==========================================
st.header("新しく記録する")

# 名前選択
existing_names = []
if not df.empty and '名前' in df.columns:
    existing_names = sorted(df['名前'].unique().tolist())
name_options = existing_names + ["➕ 新規登録"]
selected_name_option = st.selectbox("名前を選択してください", name_options, key="name_selector")

if selected_name_option == "➕ 新規登録":
    user_name = st.text_input("新しい名前を入力", key="new_name_input")
else:
    user_name = selected_name_option

if not user_name:
    st.info("名前を選択するか、新しく入力してください。")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    input_date = st.date_input('日付', datetime.today())
with col2:
    input_weight = st.number_input('体重 (kg)', min_value=0.0, step=0.1, format="%.1f")

# 身長入力（オプション）
update_height = st.checkbox("身長を登録・更新する")
input_height = None

if update_height:
    current_height_val = 160.0
    if not df.empty and '身長_filled' in df.columns:
        user_data = df[df['名前'] == user_name]
        if not user_data.empty:
            last_h = user_data['身長_filled'].iloc[-1]
            if pd.notna(last_h):
                current_height_val = float(last_h)
    
    input_height = st.number_input('身長 (cm)', min_value=0.0, step=0.1, value=current_height_val, format="%.1f")

if st.button("保存"):
    if input_weight == 0.0 and not update_height:
        st.error("「体重を入力」するか、「身長を更新」してください。")
    else:
        date_str = input_date.strftime('%Y-%m-%d')
        weight_to_save = input_weight if input_weight > 0 else ""
        height_to_save = input_height if update_height else ""
        
        # 1. 新規行を追加
        row_data = [date_str, weight_to_save, user_name, height_to_save]
        worksheet.append_row(row_data)
        
        msg = f"{user_name} さんのデータを保存しました！"
        
        # 2. ★追加機能：過去の空白身長データを埋める処理
        if update_height and input_height > 0:
            try:
                # 全データを取得してチェック
                all_vals = worksheet.get_all_values()
                header = all_vals[0]
                
                # 列の位置を確認
                try:
                    name_idx = header.index("名前")
                    height_idx = header.index("身長")
                except ValueError:
                    # 身長列などが無い場合はスキップ
                    name_idx = -1
                
                if name_idx != -1 and height_idx != -1:
                    cells_to_update = []
                    
                    # 2行目から順にチェック
                    for i, row in enumerate(all_vals):
                        if i == 0: continue # ヘッダー読み飛ばし
                        
                        # 行の長さが足りない場合を考慮して値を取得
                        row_name = row[name_idx] if len(row) > name_idx else ""
                        row_height = row[height_idx] if len(row) > height_idx else ""
                        
                        # 「名前が一致」かつ「身長が空」の場合
                        if row_name == user_name and (row_height == "" or row_height is None):
                            # 更新リストに追加（行番号はi+1、列番号はheight_idx+1）
                            cells_to_update.append(
                                Cell(row=i+1, col=height_idx+1, value=input_height)
                            )
                    
                    # 更新対象があれば一括更新
                    if cells_to_update:
                        worksheet.update_cells(cells_to_update)
                        msg += f"\n（過去の未入力データ {len(cells_to_update)} 件にも身長を反映しました）"
                        
            except Exception as e:
                # エラーが起きてもメインの保存はできているので、ログ表示のみにとどめる
                print(f"身長遡及更新エラー: {e}")

        if update_height:
            msg += f" (身長: {input_height}cm)"
        if input_weight == 0.0:
            msg += " ※体重は未入力です"
            
        st.success(msg)
        time.sleep(1)
        st.rerun()

st.divider()

# ==========================================
# 4. データの管理（削除・名前変更）
# ==========================================
st.header("データの管理")

# --- 名前変更機能 ---
with st.expander("登録名を変更する"):
    st.write(f"現在の名前「**{user_name}**」のデータをすべて、新しい名前に書き換えます。")
    new_name_input = st.text_input("変更後の名前を入力", key="rename_input")

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
                st.error("名前列が見つかりません")
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
                st.success(f"{count} 件変更しました！")
                st.session_state.confirm_merge = False
                time.sleep(2)
                st.rerun()
            else:
                st.warning("対象データなし")
        except Exception as e:
            st.error(f"エラー: {e}")

    if st.button("名前変更を確認"):
        if new_name_input and new_name_input != user_name:
            existing_list = df['名前'].unique().tolist() if not df.empty else []
            if new_name_input in existing_list:
                st.session_state.confirm_merge = True
                st.session_state.target_name = new_name_input
            else:
                execute_name_change(user_name, new_name_input)
        else:
            st.warning("新しい名前を入力してください")

    if st.session_state.confirm_merge:
        st.warning(f"名前「{st.session_state.target_name}」は既に存在します。統合しますか？")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("統合実行", type="primary"):
                execute_name_change(user_name, st.session_state.target_name)
        with c2:
            if st.button("キャンセル"):
                st.session_state.confirm_merge = False
                st.rerun()

# --- データ削除機能 ---
with st.expander("データを削除する"):
    if not df.empty and '名前' in df.columns:
        df['日付_str'] = df['日付'].dt.strftime('%Y-%m-%d')
        my_df = df[df['名前'] == user_name].sort_values('日付', ascending=False)
        
        if not my_df.empty:
            date_options = my_df['日付_str'].tolist()
            selected_date = st.selectbox("日付を選択", date_options, key="delete_date")
            target_data = my_df[my_df['日付_str'] == selected_date].iloc[0]
            
            w_disp = target_data.get('体重', '-')
            if pd.isna(w_disp) or w_disp == "": w_disp = "(未入力)"
            
            st.warning(f"{selected_date} の記録（体重: {w_disp}）を削除しますか？")
            
            if st.button("削除実行", type="primary"):
                try:
                    all_vals = worksheet.get_all_values()
                    header = all_vals[0]
                    name_idx = header.index("名前")
                    date_idx = header.index("日付")
                    
                    row_idx = None
                    for i, r in enumerate(all_vals):
                        if i==0: continue
                        if r[date_idx] == selected_date and r[name_idx] == user_name:
                            row_idx = i+1
                            break
                    
                    if row_idx:
                        worksheet.delete_rows(row_idx)
                        st.success("削除完了")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"削除エラー: {e}")
        else:
            st.info("データなし")
