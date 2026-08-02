import datetime
import sqlite3
import pandas as pd
import streamlit as st

# --- ページの設定 ---
st.set_page_config(
    page_title="消耗品発注システム", page_icon="📦", layout="wide"
)


# --- データベース接続関数 (SQLite) ---
def get_connection():
  # ファイル型のSQLiteデータベースに接続（存在しない場合は自動作成されます）
  conn = sqlite3.connect("water_quality.db")
  # 辞書形式でカラム名アクセスできるようにRowファクトリを設定
  conn.row_factory = sqlite3.Row
  return conn


# --- テーブル初期化関数 ---
def init_db():
  conn = get_connection()
  cursor = conn.cursor()

  # ユーザーテーブル
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        department TEXT,
        is_approver INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0
    )
    """)

  # 発注先テーブル
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_name TEXT UNIQUE NOT NULL
    )
    """)

  # 発注履歴テーブル
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT,
        department TEXT,
        order_datetime TEXT,
        item_name TEXT,
        vendor_name TEXT,
        quantity INTEGER,
        unit TEXT,
        item_code TEXT,
        remarks TEXT,
        status TEXT DEFAULT '未承認'
    )
    """)

  # 初期管理者ユーザー・初期データがない場合に追加 (必要に応じて)
  cursor.execute("SELECT COUNT(*) FROM users")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO users (username, password, name, department, is_approver,"
        " is_admin) VALUES ('admin', 'admin123', '管理者', '総務部', 1, 1)"
    )

  conn.commit()
  conn.close()


# アプリ起動時にDB初期化を実行
init_db()

# --- ログイン状態の管理 ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False

if not st.session_state.logged_in:
  st.title("消耗品発注システム - ログイン")
  username = st.text_input("ログインID")
  password = st.text_input("パスワード", type="password")
  if st.button("ログイン"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password),
    )
    user = cursor.fetchone()
    conn.close()

    if user:
      st.session_state.logged_in = True
      st.session_state.username = user["username"]
      st.session_state.name = user["name"]
      st.session_state.department = user["department"]
      st.session_state.is_approver = bool(user["is_approver"])
      st.session_state.is_admin = bool(user["is_admin"])
      st.session_state.menu_choice = 0
      st.rerun()
    else:
      st.error("IDまたはパスワードが違います。")
else:
  if "username" not in st.session_state:
    st.session_state.username = ""

  # --- ログイン後の画面 ---
  st.sidebar.write(
      f"👤 ログイン中: {st.session_state.get('name', 'ゲスト')}"
      f" ({st.session_state.get('department', '')})"
  )

  if st.sidebar.button("🔄 画面を更新する (リロード)"):
    st.session_state.menu_choice = 0
    st.rerun()

  if st.sidebar.button("ログアウト"):
    st.session_state.logged_in = False
    st.rerun()

  menu = ["発注画面", "アカウント設定"]
  if st.session_state.get("is_approver", False):
    menu.append("承認画面")
  if st.session_state.get("is_admin", False):
    menu.append("管理者画面")

  if "menu_choice" not in st.session_state:
    st.session_state.menu_choice = 0

  choice = st.sidebar.selectbox(
      "メニュー", menu, index=st.session_state.menu_choice
  )
  st.session_state.menu_choice = menu.index(choice)

  # ==========================================
  # 1. 発注画面
  # ==========================================
  if choice == "発注画面":
    st.title("📝 消耗品 発注入力")

    for key in [
        "re_item_name",
        "re_vendor_name",
        "re_unit",
        "re_item_code",
        "re_remarks",
    ]:
      if key not in st.session_state:
        st.session_state[key] = ""
    if "re_quantity" not in st.session_state:
      st.session_state.re_quantity = 1

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vendor_name FROM vendors")
    vendor_list = [""] + [row["vendor_name"] for row in cursor.fetchall()]
    conn.close()

    vendor_index = 0
    if st.session_state.re_vendor_name in vendor_list:
      vendor_index = vendor_list.index(st.session_state.re_vendor_name)

    with st.form("order_form"):
      st.text_input(
          "発注者", value=st.session_state.get("name", ""), disabled=True
      )
      st.text_input(
          "所属", value=st.session_state.get("department", ""), disabled=True
      )
      order_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      st.text_input("発注日時", value=order_datetime, disabled=True)

      item_name = st.text_input("品名", value=st.session_state.re_item_name)
      vendor_name = st.selectbox("発注先", vendor_list, index=vendor_index)

      col1, col2 = st.columns(2)
      with col1:
        quantity = st.number_input(
            "数量 (数字のみ)",
            min_value=1,
            step=1,
            value=st.session_state.re_quantity,
        )
      with col2:
        unit = st.text_input(
            "単位 (個、本、箱など)", value=st.session_state.re_unit
        )

      item_code = st.text_input("品番", value=st.session_state.re_item_code)
      remarks = st.text_area("備考 (用途)", value=st.session_state.re_remarks)

      submitted = st.form_submit_button("発注を申請する")

    if submitted:
      if item_name == "" or unit == "":
        st.warning("品名と単位は必ず入力してください。")
      else:
        conn = get_connection()
        cursor = conn.cursor()
        sql = """INSERT INTO orders (user_name, department, order_datetime, item_name, vendor_name, quantity, unit, item_code, remarks) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        cursor.execute(
            sql,
            (
                st.session_state.name,
                st.session_state.department,
                order_datetime,
                item_name,
                vendor_name,
                quantity,
                unit,
                item_code,
                remarks,
            ),
        )
        conn.commit()
        conn.close()
        st.success("発注申請を送信しました！")

        st.session_state.re_item_name = ""
        st.session_state.re_vendor_name = ""
        st.session_state.re_quantity = 1
        st.session_state.re_unit = ""
        st.session_state.re_item_code = ""
        st.session_state.re_remarks = ""
        st.rerun()

    st.divider()
    st.subheader("📚 あなたの過去の発注履歴（再利用できます）")

    conn = get_connection()
    sql_history = """
        SELECT id, order_datetime, item_name, quantity, unit, vendor_name, item_code, remarks, status 
        FROM orders 
        WHERE user_name = ? 
        ORDER BY order_datetime DESC
        """
    cursor = conn.cursor()
    cursor.execute(sql_history, (st.session_state.name,))
    rows = cursor.fetchall()
    conn.close()

    if len(rows) > 0:
      for row in rows:
        with st.container():
          col_info, col_btn = st.columns([4, 1])
          with col_info:
            st.write(
                f"**【{row['status']}】 {row['item_name']}**"
                f" （{row['quantity']}{row['unit']}） - 発注先:"
                f" {row['vendor_name'] or '未指定'}"
            )
            st.caption(
                f"発注日時: {row['order_datetime']} | 品番:"
                f" {row['item_code'] or 'なし'} | 備考:"
                f" {row['remarks'] or 'なし'}"
            )
          with col_btn:
            if st.button("この内容をコピー", key=f"copy_{row['id']}"):
              st.session_state.re_item_name = row["item_name"]
              st.session_state.re_vendor_name = (
                  row["vendor_name"] if row["vendor_name"] else ""
              )
              st.session_state.re_quantity = (
                  int(row["quantity"]) if row["quantity"] else 1
              )
              st.session_state.re_unit = row["unit"] if row["unit"] else ""
              st.session_state.re_item_code = (
                  row["item_code"] if row["item_code"] else ""
              )
              st.session_state.re_remarks = (
                  row["remarks"] if row["remarks"] else ""
              )
              st.rerun()
        st.divider()
    else:
      st.info("過去の発注履歴はありません。")

  # ==========================================
  # 2. アカウント設定画面
  # ==========================================
  elif choice == "アカウント設定":
    st.title("🔑 アカウント設定（ID・パスワードの変更）")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT department FROM users WHERE department IS NOT NULL"
        " AND department != ''"
    )
    dept_rows = cursor.fetchall()
    department_list = [row["department"] for row in dept_rows]

    target_uname = st.session_state.get("username", "")
    if not target_uname:
      cursor.execute(
          "SELECT * FROM users WHERE name=?", (st.session_state.get("name", ""),)
      )
    else:
      cursor.execute("SELECT * FROM users WHERE username=?", (target_uname,))
    current_user_data = cursor.fetchone()
    conn.close()

    if current_user_data:
      if current_user_data["department"] not in department_list:
        department_list.append(current_user_data["department"])

      dept_index = (
          department_list.index(current_user_data["department"])
          if current_user_data["department"] in department_list
          else 0
      )

      with st.form("account_form"):
        new_username = st.text_input(
            "ログインID", value=current_user_data["username"]
        )
        new_name = st.text_input("氏名", value=current_user_data["name"])
        new_department = st.selectbox(
            "所属部署", department_list, index=dept_index
        )

        st.divider()
        st.write(
            "パスワードを変更する場合は、新しいパスワードを入力してください。"
        )
        new_password = st.text_input(
            "新しいパスワード",
            type="password",
            value=current_user_data["password"],
        )

        submitted_account = st.form_submit_button("アカウント情報を更新する")

      if submitted_account:
        if (
            new_username.strip() == ""
            or new_password.strip() == ""
            or new_name.strip() == ""
        ):
          st.warning("ログインID、氏名、パスワードは空欄にできません。")
        else:
          conn_up = get_connection()
          cursor_up = conn_up.cursor()
          cursor_up.execute(
              "SELECT * FROM users WHERE username=? AND username != ?",
              (new_username, current_user_data["username"]),
          )
          dup_user = cursor_up.fetchone()

          if dup_user:
            st.error("そのログインIDはすでに使用されています。")
            conn_up.close()
          else:
            update_sql = (
                "UPDATE users SET username=?, password=?, name=?, department=?"
                " WHERE username=?"
            )
            cursor_up.execute(
                update_sql,
                (
                    new_username,
                    new_password,
                    new_name,
                    new_department,
                    current_user_data["username"],
                ),
            )

            if new_name != st.session_state.name:
              cursor_up.execute(
                  "UPDATE orders SET user_name=? WHERE user_name=?",
                  (new_name, st.session_state.name),
              )

            conn_up.commit()
            conn_up.close()

            st.session_state.username = new_username
            st.session_state.name = new_name
            st.session_state.department = new_department

            st.success(
                "アカウント情報を更新しました！一度ログアウトして再ログインしてください。"
            )
    else:
      st.error("ユーザー情報の取得に失敗しました。")

  # ==========================================
  # 3. 承認画面
  # ==========================================
  elif choice == "承認画面":
    st.title("✅ 承認待ち ＆ 処理済一覧")
    st.write(f"【{st.session_state.department}】の発注申請")

    conn = get_connection()
    cursor = conn.cursor()

    st.subheader("⏳ 承認待ちの発注")
    cursor.execute(
        "SELECT id, order_datetime, user_name, item_name, quantity, unit,"
        " remarks FROM orders WHERE department=? AND status='未承認'",
        (st.session_state.department,),
    )
    pending_rows = cursor.fetchall()

    if len(pending_rows) > 0:
      for row in pending_rows:
        st.write(
            f"**{row['order_datetime']} | {row['user_name']} | 品名:"
            f" {row['item_name']} ({row['quantity']}{row['unit']})**"
        )
        st.caption(f"備考: {row['remarks'] or 'なし'}")

        col1, col2 = st.columns([1, 1])
        with col1:
          if st.button("承認する", key=f"btn_approve_{row['id']}"):
            cursor.execute(
                "UPDATE orders SET status='承認済' WHERE id=?", (row["id"],)
            )
            conn.commit()
            conn.close()
            st.rerun()
        with col2:
          if st.button("差し戻し", key=f"btn_reject_{row['id']}"):
            cursor.execute(
                "UPDATE orders SET status='差し戻し' WHERE id=?", (row["id"],)
            )
            conn.commit()
            conn.close()
            st.rerun()
        st.divider()
    else:
      st.info("現在、承認待ちの発注はありません。")
      st.divider()

    st.subheader("📚 過去に処理した発注一覧")
    cursor.execute(
        """
            SELECT 
                order_datetime AS '発注日時', 
                user_name AS '発注者', 
                item_name AS '品名', 
                quantity AS '数量', 
                unit AS '単位', 
                vendor_name AS '発注先', 
                status AS 'ステータス'
            FROM orders 
            WHERE department=? AND status IN ('承認済', '発注済み', '差し戻し') 
            ORDER BY order_datetime DESC
            """,
        (st.session_state.department,),
    )
    processed_rows = cursor.fetchall()
    conn.close()

    if len(processed_rows) > 0:
      df_processed = pd.DataFrame([dict(r) for r in processed_rows])
      st.dataframe(df_processed, use_container_width=True)
    else:
      st.info("過去に処理した発注はまだありません。")

  # ==========================================
  # 4. 管理者画面
  # ==========================================
  elif choice == "管理者画面":
    st.title("⚙️ 管理者メニュー")

    st.subheader("📦 発注先ごとのデータ抽出 & ステータス管理")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vendor_name FROM vendors")
    vendor_list = [row["vendor_name"] for row in cursor.fetchall()]
    conn.close()

    if len(vendor_list) > 0:
      selected_vendor = st.selectbox("発注先を選択して抽出", vendor_list)

      conn = get_connection()
      cursor = conn.cursor()
      sql_admin = """
            SELECT id, order_datetime, department, user_name, item_name, item_code, quantity, unit, remarks, vendor_name, TRIM(status) AS status 
            FROM orders 
            WHERE vendor_name = ? AND TRIM(status) IN ('承認済', '発注済み', '納品済', '検収済')
            ORDER BY id DESC
            """
      cursor.execute(sql_admin, (selected_vendor,))
      admin_rows = cursor.fetchall()
      conn.close()

      if len(admin_rows) > 0:
        for row in admin_rows:
          with st.container():
            col_info, col_action = st.columns([2.5, 1.5])
            with col_info:
              st.write(
                  f"**【現在のステータス: {row['status']}】 {row['item_name']}**"
                  f" （{row['quantity']}{row['unit']}）"
              )
              st.caption(
                  f"発注日時: {row['order_datetime']} | 部署: {row['department']}"
                  f" | 担当者: {row['user_name']} | 品番:"
                  f" {row['item_code'] or 'なし'}"
              )
              if row["remarks"]:
                st.caption(f"備考: {row['remarks']}")

              current_v_index = (
                  vendor_list.index(row["vendor_name"])
                  if row["vendor_name"] in vendor_list
                  else 0
              )
              new_assigned_vendor = st.selectbox(
                  "発注先の変更",
                  vendor_list,
                  index=current_v_index,
                  key=f"change_v_box_{row['id']}",
              )
              if new_assigned_vendor != row["vendor_name"]:
                if st.button(
                    "発注先を更新する",
                    key=f"update_v_btn_{row['id']}_{selected_vendor}",
                ):
                  conn_chg = get_connection()
                  cursor_chg = conn_chg.cursor()
                  cursor_chg.execute(
                      "UPDATE orders SET vendor_name=? WHERE id=?",
                      (new_assigned_vendor, row["id"]),
                  )
                  conn_chg.commit()
                  conn_chg.close()
                  st.success("発注先を変更しました！")
                  st.rerun()

            with col_action:
              st.markdown("**🔄 ステータス変更**")
              status_options = ["承認済", "発注済み", "納品済", "検収済"]
              current_s_index = (
                  status_options.index(row["status"])
                  if row["status"] in status_options
                  else 0
              )

              new_status = st.selectbox(
                  "ステータス選択",
                  status_options,
                  index=current_s_index,
                  label_visibility="collapsed",
                  key=f"change_s_box_{row['id']}",
              )

              if new_status != row["status"]:
                conn_s = get_connection()
                cursor_s = conn_s.cursor()
                cursor_s.execute(
                    "UPDATE orders SET status=? WHERE id=?",
                    (new_status, row["id"]),
                )
                conn_s.commit()
                conn_s.close()
                st.success(f"「{new_status}」に変更しました！")
                st.rerun()

            st.divider()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql_admin, (selected_vendor,))
        admin_rows_fresh = cursor.fetchall()
        conn.close()

        csv_rows = [
            row for row in admin_rows_fresh if row["status"] == "承認済"
        ]

        if len(csv_rows) > 0:
          df_csv = pd.DataFrame([dict(r) for r in csv_rows])
          df_csv = df_csv.drop(columns=["id"])
          df_csv = df_csv[[
              "order_datetime",
              "department",
              "user_name",
              "item_name",
              "item_code",
              "quantity",
              "unit",
              "remarks",
              "vendor_name",
              "status",
          ]]
          df_csv.columns = [
              "発注日時",
              "所属",
              "発注者",
              "品名",
              "品番",
              "数量",
              "単位",
              "備考",
              "発注先",
              "ステータス",
          ]

          csv = df_csv.to_csv(index=False).encode(
              "shift-jis", errors="replace"
          )
          st.download_button(
              label="📥 【承認済のみ】エクセル(CSV)でダウンロードする",
              data=csv,
              file_name=f"{selected_vendor}_発注一覧_承認済.csv",
              mime="text/csv",
          )

          st.divider()

          copy_text_lines = [
              f"発注者: {r['user_name']} | 品名: {r['item_name']} | 数量:"
              f" {r['quantity']}{r['unit']} | 備考: {r['remarks'] or 'なし'}"
              for r in csv_rows
          ]
          st.markdown(
              "### 📋 【承認済】テキスト表示エリア（コピーしてご利用ください）"
          )
          st.text_area(
              "コピペ用テキスト（発注者・品名・数量・単位・備考）",
              value="\n".join(copy_text_lines),
              height=150,
              key=f"copy_area_{selected_vendor}",
          )

          if st.button(
              "📋 ステータスをすべて『発注済み』に変更する",
              key=f"btn_mark_ordered_{selected_vendor}",
              type="primary",
          ):
            conn_ord = get_connection()
            cursor_ord = conn_ord.cursor()
            for r in csv_rows:
              cursor_ord.execute(
                  "UPDATE orders SET status='発注済み' WHERE id=?", (r["id"],)
              )
            conn_ord.commit()
            conn_ord.close()

            for r in csv_rows:
              if f"change_s_box_{r['id']}" in st.session_state:
                del st.session_state[f"change_s_box_{r['id']}"]

            st.success("すべての対象データを「発注済み」に変更しました！")
            st.rerun()
        else:
          st.info(
              "ℹ️ 現在、この発注先には「承認済（未発注）」のデータはありません。"
          )
      else:
        st.warning("この発注先への対象データはありません。")
    else:
      st.info(
          "登録されている発注先がありません。下のフォームから追加してください。"
      )

    # 未指定コーナー
    st.divider()
    st.subheader("⚠️ 【発注先未指定】の申請一覧")

    conn_none = get_connection()
    cursor_none = conn_none.cursor()
    sql_none = """
        SELECT id, order_datetime, department, user_name, item_name, item_code, quantity, unit, remarks, vendor_name, TRIM(status) AS status 
        FROM orders 
        WHERE (vendor_name IS NULL OR vendor_name = '' OR vendor_name NOT IN (SELECT vendor_name FROM vendors)) 
          AND TRIM(status) IN ('承認済', '発注済み', '納品済', '検収済')
        ORDER BY id DESC
        """
    cursor_none.execute(sql_none)
    none_rows = cursor_none.fetchall()
    conn_none.close()

    if len(none_rows) > 0:
      st.warning("発注先が選択されていない申請データが見つかりました。")
      for row in none_rows:
        with st.container():
          col_info, col_action = st.columns([2.5, 1.5])
          with col_info:
            st.write(
                f"**【現在のステータス: {row['status']}】 {row['item_name']}**"
                f" （{row['quantity']}{row['unit']}）"
            )
            st.caption(
                f"発注日時: {row['order_datetime']} | 部署: {row['department']}"
                f" | 担当者: {row['user_name']} | 品番:"
                f" {row['item_code'] or 'なし'}"
            )
            if row["remarks"]:
              st.caption(f"備考: {row['remarks']}")

            assign_v = st.selectbox(
                "発注先を割り当てる",
                [""] + vendor_list,
                key=f"assign_v_box_{row['id']}",
            )
            if assign_v != "":
              if st.button(
                  "この発注先に設定する", key=f"assign_v_btn_{row['id']}"
              ):
                conn_asg = get_connection()
                cursor_asg = conn_asg.cursor()
                cursor_asg.execute(
                    "UPDATE orders SET vendor_name=? WHERE id=?",
                    (assign_v, row["id"]),
                )
                conn_asg.commit()
                conn_asg.close()
                st.success(f"発注先を「{assign_v}」に設定しました！")
                st.rerun()

          with col_action:
            st.markdown("**🔄 ステータス変更**")
            status_options = ["承認済", "発注済み", "納品済", "検収済"]
            current_s_index = (
                status_options.index(row["status"])
                if row["status"] in status_options
                else 0
            )

            new_status = st.selectbox(
                "ステータス選択",
                status_options,
                index=current_s_index,
                label_visibility="collapsed",
                key=f"change_s_none_box_{row['id']}",
            )

            if new_status != row["status"]:
              conn_s = get_connection()
              cursor_s = conn_s.cursor()
              cursor_s.execute(
                  "UPDATE orders SET status=? WHERE id=?",
                  (new_status, row["id"]),
              )
              conn_s.commit()
              conn_s.close()
              st.success(f"「{new_status}」に変更しました！")
              st.rerun()
          st.divider()
    else:
      st.info("現在、発注先が未指定の申請データはありません。")

    st.divider()
    st.subheader("🛠️ 発注先の管理（追加・変更・削除）")
    tab_add, tab_edit = st.tabs(["発注先の追加", "発注先の変更・削除"])

    with tab_add:
      new_vendor = st.text_input(
          "新しい発注先名を入力", key="new_vendor_input"
      )
      if st.button("発注先を追加する", key="add_vendor_btn"):
        if new_vendor.strip() == "":
          st.warning("発注先名を入力してください。")
        else:
          conn_add = get_connection()
          cursor_add = conn_add.cursor()
          cursor_add.execute(
              "SELECT * FROM vendors WHERE vendor_name=?", (new_vendor,)
          )
          exists = cursor_add.fetchone()
          if exists:
            st.warning("すでに登録されている発注先です。")
          else:
            cursor_add.execute(
                "INSERT INTO vendors (vendor_name) VALUES (?)", (new_vendor,)
            )
            conn_add.commit()
            st.success(f"「{new_vendor}」を追加しました！")
            st.rerun()
          conn_add.close()

    with tab_edit:
      if len(vendor_list) > 0:
        target_vendor = st.selectbox(
            "変更・削除する発注先を選択",
            vendor_list,
            key="target_vendor_selectbox",
        )
        edit_vendor_name = st.text_input(
            "新しい発注先名（変更する場合に入力）",
            value=target_vendor,
            key="edit_vendor_input",
        )

        col_e1, col_e2 = st.columns(2)
        with col_e1:
          if st.button("発注先名を変更する", key="update_vendor_btn"):
            if edit_vendor_name.strip() == "":
              st.warning("変更後の名前を入力してください。")
            else:
              conn_ed = get_connection()
              cursor_ed = conn_ed.cursor()
              cursor_ed.execute(
                  "UPDATE vendors SET vendor_name=? WHERE vendor_name=?",
                  (edit_vendor_name, target_vendor),
              )
              cursor_ed.execute(
                  "UPDATE orders SET vendor_name=? WHERE vendor_name=?",
                  (edit_vendor_name, target_vendor),
              )
              conn_ed.commit()
              conn_ed.close()
              st.success(
                  f"発注先名を「{edit_vendor_name}」に変更しました！"
              )
              st.rerun()
        with col_e2:
          if st.button(
              "この発注先を削除する", type="primary", key="delete_vendor_btn"
          ):
            conn_del = get_connection()
            cursor_del = conn_del.cursor()
            cursor_del.execute(
                "DELETE FROM vendors WHERE vendor_name=?", (target_vendor,)
            )
            conn_del.commit()
            conn_del.close()
            st.success(f"発注先「{target_vendor}」を削除しました。")
            st.rerun()
      else:
        st.info("変更・削除できる発注先がありません。")