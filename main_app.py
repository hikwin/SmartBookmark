import os
import sqlite3
import webbrowser
import threading
import hashlib
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb
from ttkbootstrap.constants import *

import database
import bookmark_parser
import bookmark_processor
import classifier

DB_PATH = "bookmarks.db"

class BookmarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chrome 书签智能整理助手")
        self.root.geometry("1300x800")
        
        # Initialize database
        database.init_db(DB_PATH)
        
        # Threads control
        self.check_thread = None
        self.check_cancelled = False
        
        # Selected states
        self.current_folder = "All"
        self.current_category = "All"
        self.current_status_filter = "All"  # "All", "Valid", "Invalid", "Untested"
        self.checked_bookmark_ids = set()  # Set of checked bookmark IDs
        self.updating_selection = False    # Guard flag to prevent event loops
        
        self.create_styles()
        self.build_ui()
        self.load_data_dashboard()

    def create_styles(self):
        style = tb.Style()
        # Ensure Treeview has modern rowheight
        style.configure("Treeview", rowheight=28, font=("Microsoft YaHei", 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei", 10, "bold"))
        
        # Configure Notebook Tab styling: selected tab is primary blue, unselected is theme bg
        primary_color = style.colors.primary
        bg_color = style.colors.bg
        
        for style_name in ["TNotebook.Tab", "primary.TNotebook.Tab", "Primary.TNotebook.Tab"]:
            style.configure(style_name, font=("Microsoft YaHei", 10), padding=[15, 6])
            style.map(style_name,
                background=[("selected", primary_color), ("active", "#3a4f66"), ("!selected", bg_color)],
                lightcolor=[("selected", primary_color), ("active", "#3a4f66"), ("!selected", bg_color)],
                foreground=[("selected", "#ffffff"), ("!selected", "#a6b0cf")]
            )
        
    def build_ui(self):
        # Main container
        main_container = tb.Frame(self.root, padding=10)
        main_container.pack(fill=BOTH, expand=YES)
        
        # ==================== 1. TOP TOOLBAR ====================
        toolbar = tb.Frame(main_container, padding=5)
        toolbar.pack(fill=X, side=TOP, pady=(0, 10))
        
        btn_import = tb.Button(toolbar, text="📂 导入书签", bootstyle="primary", command=self.import_bookmarks)
        btn_import.pack(side=LEFT, padx=5)
        
        btn_export = tb.Button(toolbar, text="📤 导出书签", bootstyle="success", command=self.export_bookmarks)
        btn_export.pack(side=LEFT, padx=5)
        
        tb.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)
        
        self.btn_check = tb.Button(toolbar, text="🟢 一键检测网址", bootstyle="info", command=self.start_validity_check)
        self.btn_check.pack(side=LEFT, padx=5)
        
        btn_classify = tb.Button(toolbar, text="🤖 AI智能分类", bootstyle="warning", command=self.run_ai_classify)
        btn_classify.pack(side=LEFT, padx=5)
        
        btn_dedup = tb.Button(toolbar, text="✂️ 去重整理", bootstyle="secondary", command=self.run_deduplicate)
        btn_dedup.pack(side=LEFT, padx=5)
        
        btn_del_inv = tb.Button(toolbar, text="🔴 删除选中失效", bootstyle="danger", command=self.delete_invalid)
        btn_del_inv.pack(side=LEFT, padx=5)
        
        tb.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)
        
        self.btn_undo = tb.Button(toolbar, text="↩️ 撤回上一步", bootstyle="light-outline", command=self.undo_operation)
        self.btn_undo.pack(side=LEFT, padx=5)
        
        self.btn_restore = tb.Button(toolbar, text="🔄 还原初始书签", bootstyle="warning-outline", command=self.restore_initial)
        self.btn_restore.pack(side=LEFT, padx=5)
        
        self.btn_clear = tb.Button(toolbar, text="🧹 清空导入数据", bootstyle="danger-outline", command=self.clear_database)
        self.btn_clear.pack(side=LEFT, padx=5)
        
        # ==================== 2. STATS CARDS ====================
        stats_frame = tb.Frame(main_container)
        stats_frame.pack(fill=X, side=TOP, pady=(0, 10))
        
        # We will use 4 cards: Total, Folders, Duplicates, Invalid
        self.card_total = self.create_stat_card(stats_frame, "总书签数", "0", "primary", 0)
        self.card_folders = self.create_stat_card(stats_frame, "文件夹数", "0", "info", 1)
        self.card_duplicates = self.create_stat_card(stats_frame, "重复链接", "0", "warning", 2)
        self.card_invalid = self.create_stat_card(stats_frame, "失效链接", "0", "danger", 3)
        
        # ==================== 3. BODY AREA ====================
        body_pane = tb.Frame(main_container)
        body_pane.pack(fill=BOTH, expand=YES, side=TOP)
        
        # Left Panel (Navigation list)
        left_panel = tb.Frame(body_pane, width=280, padding=5)
        left_panel.pack(fill=Y, side=LEFT, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Left Panel Notebook (Folders / Categories)
        left_notebook = tb.Notebook(left_panel, bootstyle="primary")
        left_notebook.pack(fill=BOTH, expand=YES)
        
        # Folders Tab
        tab_folders = tb.Frame(left_notebook)
        left_notebook.add(tab_folders, text="📁 文件夹")
        
        self.folder_tree = ttk.Treeview(tab_folders, show="tree", selectmode="browse")
        self.folder_tree.pack(fill=BOTH, expand=YES, side=LEFT)
        folder_scroll = tb.Scrollbar(tab_folders, orient=VERTICAL, command=self.folder_tree.yview)
        folder_scroll.pack(fill=Y, side=RIGHT)
        self.folder_tree.configure(yscrollcommand=folder_scroll.set)
        self.folder_tree.bind("<<TreeviewSelect>>", self.on_folder_select)
        
        # Categories Tab
        tab_categories = tb.Frame(left_notebook)
        left_notebook.add(tab_categories, text="🏷️ AI分类")
        
        self.category_list = tk.Listbox(
            tab_categories,
            font=("Microsoft YaHei", 10),
            bg="#22252a",
            fg="#ffffff",
            selectbackground="#3498db",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False
        )
        self.category_list.pack(fill=BOTH, expand=YES, side=LEFT)
        category_scroll = tb.Scrollbar(tab_categories, orient=VERTICAL, command=self.category_list.yview)
        category_scroll.pack(fill=Y, side=RIGHT)
        self.category_list.configure(yscrollcommand=category_scroll.set)
        self.category_list.bind("<<ListboxSelect>>", self.on_category_select)
        
        # Right Panel (Bookmarks grid)
        right_panel = tb.Frame(body_pane, padding=5)
        right_panel.pack(fill=BOTH, expand=YES, side=LEFT)
        
        # Filters and Search
        filter_bar = tb.Frame(right_panel, padding=5)
        filter_bar.pack(fill=X, side=TOP, pady=(0, 10))
        
        tb.Label(filter_bar, text="🔍 搜索:").pack(side=LEFT, padx=(0, 5))
        self.search_entry = tb.Entry(filter_bar, width=25)
        self.search_entry.pack(side=LEFT, padx=(0, 15))
        self.search_entry.bind("<KeyRelease>", lambda event: self.filter_bookmarks())
        
        tb.Label(filter_bar, text="状态过滤:").pack(side=LEFT, padx=(0, 5))
        self.filter_status = tb.Combobox(
            filter_bar,
            values=[
                "全部状态",
                "🟢 所有有效链接",
                "🔴 所有失效链接",
                "🟢 成功 (200 OK)",
                "🔴 页面丢失 (404)",
                "🔴 拒绝访问 (403)",
                "🔴 服务器错误 (50x)",
                "🔴 超时/网络异常",
                "⚪ 未检测"
            ],
            state="readonly",
            width=18
        )
        self.filter_status.current(0)
        self.filter_status.pack(side=LEFT, padx=(0, 15))
        self.filter_status.bind("<<ComboboxSelected>>", self.on_status_filter_change)
        
        # Select All checkbox
        self.var_select_all = tk.BooleanVar(value=False)
        self.chk_select_all = tb.Checkbutton(filter_bar, text="全选", variable=self.var_select_all, bootstyle="round-toggle", command=self.toggle_select_all)
        self.chk_select_all.pack(side=LEFT, padx=(0, 15))
        
        # Refresh Button
        btn_refresh = tb.Button(filter_bar, text="🔄 刷新列表", bootstyle="secondary-outline", command=self.filter_bookmarks)
        btn_refresh.pack(side=RIGHT, padx=5)
        
        # Bookmarks Grid
        grid_frame = tb.Frame(right_panel)
        grid_frame.pack(fill=BOTH, expand=YES, side=TOP)
        
        columns = ("select", "status", "title", "url", "category", "add_date", "folder")
        self.bm_tree = ttk.Treeview(
            grid_frame,
            columns=columns,
            show="headings",
            selectmode="extended"
        )
        
        # Column Headings & Configs
        self.bm_tree.heading("select", text="选择")
        self.bm_tree.heading("status", text="状态", command=lambda: self.sort_treeview("status", False))
        self.bm_tree.heading("title", text="标题", command=lambda: self.sort_treeview("title", False))
        self.bm_tree.heading("url", text="网址", command=lambda: self.sort_treeview("url", False))
        self.bm_tree.heading("category", text="AI分类", command=lambda: self.sort_treeview("category", False))
        self.bm_tree.heading("add_date", text="添加日期", command=lambda: self.sort_treeview("add_date", False))
        self.bm_tree.heading("folder", text="文件夹", command=lambda: self.sort_treeview("folder", False))
        
        self.bm_tree.column("select", width=50, anchor=CENTER)
        self.bm_tree.column("status", width=70, anchor=CENTER)
        self.bm_tree.column("title", width=250, anchor=W)
        self.bm_tree.column("url", width=300, anchor=W)
        self.bm_tree.column("category", width=110, anchor=CENTER)
        self.bm_tree.column("add_date", width=150, anchor=CENTER)
        self.bm_tree.column("folder", width=180, anchor=W)
        
        self.bm_tree.pack(fill=BOTH, expand=YES, side=LEFT)
        
        grid_scroll = tb.Scrollbar(grid_frame, orient=VERTICAL, command=self.bm_tree.yview)
        grid_scroll.pack(fill=Y, side=RIGHT)
        self.bm_tree.configure(yscrollcommand=grid_scroll.set)
        
        self.bm_tree.bind("<<TreeviewSelect>>", self.on_bookmark_select)
        self.bm_tree.bind("<Double-1>", self.on_bookmark_double_click)
        self.bm_tree.bind("<Button-3>", self.show_context_menu)
        self.bm_tree.bind("<Button-1>", self.on_tree_click)
        
        # Details Panel
        self.details_frame = tb.LabelFrame(right_panel, text="书签详情")
        self.details_frame.pack(fill=X, side=BOTTOM, pady=(10, 0))
        
        # Details Inner Container (for padding)
        details_inner = tb.Frame(self.details_frame, padding=10)
        details_inner.pack(fill=BOTH, expand=YES)
        
        self.lbl_det_title = tb.Label(details_inner, text="标题: -", font=("Microsoft YaHei", 10, "bold"), anchor=W)
        self.lbl_det_title.pack(fill=X, pady=2)
        
        self.lbl_det_url = tb.Label(details_inner, text="网址: -", font=("Microsoft YaHei", 9), anchor=W, foreground="#3498db", cursor="hand2")
        self.lbl_det_url.pack(fill=X, pady=2)
        self.lbl_det_url.bind("<Button-1>", lambda event: webbrowser.open(self.lbl_det_url.cget("text")[4:]))
        
        info_sub_frame = tb.Frame(details_inner)
        info_sub_frame.pack(fill=X, pady=2)
        
        self.lbl_det_folder = tb.Label(info_sub_frame, text="文件夹: -", font=("Microsoft YaHei", 9))
        self.lbl_det_folder.pack(side=LEFT, padx=(0, 20))
        
        self.lbl_det_cat = tb.Label(info_sub_frame, text="分类: -", font=("Microsoft YaHei", 9))
        self.lbl_det_cat.pack(side=LEFT, padx=(0, 20))
        
        self.lbl_det_status = tb.Label(info_sub_frame, text="HTTP状态: -", font=("Microsoft YaHei", 9))
        self.lbl_det_status.pack(side=LEFT, padx=(0, 20))
        
        self.lbl_det_time = tb.Label(info_sub_frame, text="最后检测: -", font=("Microsoft YaHei", 9))
        self.lbl_det_time.pack(side=LEFT)
        
        # ==================== 4. STATUS & PROGRESS BAR ====================
        self.status_bar = tb.Frame(main_container, padding=5)
        self.status_bar.pack(fill=X, side=BOTTOM, pady=(5, 0))
        
        self.lbl_status = tb.Label(self.status_bar, text="系统就绪", font=("Microsoft YaHei", 9))
        self.lbl_status.pack(side=LEFT)
        
        self.progress = tb.Progressbar(self.status_bar, orient=HORIZONTAL, mode='determinate', length=200, bootstyle="success")
        self.progress.pack(side=RIGHT, padx=10)
        self.progress.pack_forget() # hide initially
        
        self.btn_cancel = tb.Button(self.status_bar, text="取消检测", bootstyle="danger-outline", command=self.cancel_validity_check)
        self.btn_cancel.pack(side=RIGHT, padx=5)
        self.btn_cancel.pack_forget() # hide initially
        
        # Right Click Context Menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🌐 浏览器打开", command=self.open_selected_in_browser)
        self.context_menu.add_command(label="✏️ 修改书签标题/网址", command=self.edit_selected_bookmark)
        self.context_menu.add_command(label="🏷️ 重新分类", command=self.manual_classify_bookmark)
        self.context_menu.add_command(label="❌ 删除书签", command=self.delete_selected_bookmark)

    def create_stat_card(self, parent, title, val, boot_style, col):
        card = tb.Frame(parent, bootstyle=boot_style, padding=15)
        card.grid(row=0, column=col, sticky="nsew", padx=8, pady=5)
        parent.columnconfigure(col, weight=1)
        
        lbl_title = tb.Label(card, text=title, font=("Microsoft YaHei", 10, "bold"), bootstyle=f"inverse-{boot_style}")
        lbl_title.pack(anchor=W)
        
        lbl_val = tb.Label(card, text=val, font=("Helvetica", 26, "bold"), bootstyle=f"inverse-{boot_style}")
        lbl_val.pack(anchor=E, pady=(10, 0))
        
        return lbl_val

    # ==================== CONTROLLER LOGIC ====================
    def load_data_dashboard(self):
        """
        Reload statistics dashboard and navigation tree/list values.
        """
        self.updating_selection = True
        try:
            conn = database.get_db_connection(DB_PATH)
            cursor = conn.cursor()
            
            # 1. Stats numbers
            cursor.execute("SELECT COUNT(*) as total FROM bookmarks")
            total = cursor.fetchone()['total']
            self.card_total.configure(text=str(total))
            
            cursor.execute("SELECT COUNT(DISTINCT folder) as folders FROM bookmarks")
            folders_cnt = cursor.fetchone()['folders']
            self.card_folders.configure(text=str(folders_cnt))
            
            # Duplicates
            cursor.execute("SELECT COUNT(*) as dup_cnt FROM bookmarks WHERE hash IN (SELECT hash FROM bookmarks GROUP BY hash HAVING COUNT(*) > 1)")
            duplicates = cursor.fetchone()['dup_cnt']
            self.card_duplicates.configure(text=str(duplicates))
            
            # Invalid
            cursor.execute("SELECT COUNT(*) as invalid FROM bookmarks WHERE is_valid = 0")
            invalid = cursor.fetchone()['invalid']
            self.card_invalid.configure(text=str(invalid))
            
            # 2. Folder Navigation Tree
            self.folder_tree.delete(*self.folder_tree.get_children())
            self.folder_tree.insert("", "end", "All", text="📁 所有文件夹 (默认)")
            
            cursor.execute("SELECT DISTINCT folder FROM bookmarks ORDER BY folder ASC")
            folders = [r['folder'] for r in cursor.fetchall() if r['folder']]
            
            # Add to folder hierarchy
            # A folder might be like "Bookmarks Bar / FolderA / SubFolder"
            for folder in folders:
                if not folder:
                    continue
                parts = folder.split(" / ")
                parent = "All"
                for i in range(len(parts)):
                    node_id = " / ".join(parts[:i+1])
                    node_text = parts[i]
                    if not self.folder_tree.exists(node_id):
                        self.folder_tree.insert(parent, "end", node_id, text=f"📁 {node_text}")
                    parent = node_id
                    
            self.folder_tree.item("All", open=True)
            
            # 3. AI Category list
            self.category_list.delete(0, END)
            self.category_list.insert(END, "🏷️ 所有分类 (默认)")
            
            cursor.execute("SELECT DISTINCT category FROM bookmarks ORDER BY category ASC")
            categories = [r['category'] for r in cursor.fetchall() if r['category']]
            
            for cat in categories:
                cursor.execute("SELECT COUNT(*) as cat_cnt FROM bookmarks WHERE category = ?", (cat,))
                cnt = cursor.fetchone()['cat_cnt']
                self.category_list.insert(END, f"{cat} ({cnt})")
                
            # Select first items
            self.category_list.selection_clear(0, END)
            self.category_list.selection_set(0)
            
            # Check Undo/Restore buttons states
            cursor.execute("SELECT MAX(version) as max_ver FROM operation_history")
            row = cursor.fetchone()
            max_ver = row['max_ver'] if row else None
            
            if max_ver is not None and max_ver > 0:
                self.btn_undo.configure(state=NORMAL)
                self.btn_restore.configure(state=NORMAL)
            else:
                self.btn_undo.configure(state=DISABLED)
                self.btn_restore.configure(state=DISABLED)
                
            conn.close()
        finally:
            self.updating_selection = False
            
        self.filter_bookmarks()

    def filter_bookmarks(self):
        """
        Reads search input, active folder, active category, and status filters, then loads data to bookmarks list.
        """
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        
        search_query = self.search_entry.get().strip()
        status_filter_idx = self.filter_status.current()
        
        sql = "SELECT id, url, title, folder, category, add_date, status_code, is_valid, last_checked FROM bookmarks WHERE 1=1"
        params = []
        
        # Folder filter
        if self.current_folder != "All":
            # Folder filters subfolders too
            sql += " AND (folder = ? OR folder LIKE ?)"
            params.append(self.current_folder)
            params.append(self.current_folder + " / %")
            
        # Category filter
        if self.current_category != "All":
            sql += " AND category = ?"
            params.append(self.current_category)
            
        # Status filter
        if status_filter_idx == 1:    # All Valid
            sql += " AND is_valid = 1"
        elif status_filter_idx == 2:  # All Invalid
            sql += " AND is_valid = 0"
        elif status_filter_idx == 3:  # 200 OK
            sql += " AND is_valid = 1 AND (status_code >= 200 AND status_code < 400)"
        elif status_filter_idx == 4:  # 404 Not Found
            sql += " AND status_code = 404"
        elif status_filter_idx == 5:  # 403 Forbidden
            sql += " AND status_code = 403"
        elif status_filter_idx == 6:  # 500 / 502 / 503 / 504
            sql += " AND status_code IN (500, 502, 503, 504)"
        elif status_filter_idx == 7:  # Timeout / Net error / Protocol error
            sql += " AND status_code IN (-1, -2, -9)"
        elif status_filter_idx == 8:  # Untested
            sql += " AND is_valid = -1"
            
        # Search query
        if search_query:
            sql += " AND (title LIKE ? OR url LIKE ?)"
            params.append(f"%{search_query}%")
            params.append(f"%{search_query}%")
            
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Populate Treeview
        self.bm_tree.delete(*self.bm_tree.get_children())
        
        for r in rows:
            is_valid = r['is_valid']
            status_indicator = "⚪ 未检测"
            if is_valid == 1:
                status_indicator = f"🟢 {r['status_code'] or 200}"
            elif is_valid == 0:
                # If DNS/SSL failed, status_code is negative
                code = r['status_code']
                if code == -1:
                    status_indicator = "🔴 超时"
                elif code == -2:
                    status_indicator = "🔴 协议错误"
                elif code == -9:
                    status_indicator = "🔴 网络错误"
                else:
                    status_indicator = f"🔴 {code}"
                    
            iid_str = str(r['id'])
            select_indicator = "✅" if iid_str in self.checked_bookmark_ids else "⬜"
            
            self.bm_tree.insert(
                "",
                "end",
                iid=iid_str,
                values=(
                    select_indicator,
                    status_indicator,
                    r['title'],
                    r['url'],
                    r['category'],
                    r['add_date'],
                    r['folder']
                )
            )
            
        conn.close()
        self.lbl_status.configure(text=f"已加载 {len(rows)} 条书签")

    # ==================== NAVIGATION CLICK HANDLERS ====================
    def on_folder_select(self, event):
        if self.updating_selection:
            return
        selected = self.folder_tree.selection()
        if not selected:
            # Selection was cleared programmatically, do nothing
            return
            
        self.updating_selection = True
        try:
            self.current_folder = selected[0]
            # Reset category selection to all
            self.current_category = "All"
            self.category_list.selection_clear(0, END)
            self.category_list.selection_set(0)
            self.filter_bookmarks()
        finally:
            self.updating_selection = False

    def on_category_select(self, event):
        if self.updating_selection:
            return
        selected_idx = self.category_list.curselection()
        if selected_idx:
            self.updating_selection = True
            try:
                val = self.category_list.get(selected_idx[0])
                if selected_idx[0] == 0:
                    self.current_category = "All"
                else:
                    # Extract category name, e.g. "🛠️ 开发工具 (23)" -> "🛠️ 开发工具"
                    self.current_category = val.rsplit(" (", 1)[0]
                    
                # Reset folder selection by clearing treeview selection
                # This triggers on_folder_select asynchronously with empty tuple, which immediately returns.
                self.current_folder = "All"
                self.folder_tree.selection_set(())
                self.filter_bookmarks()
            finally:
                self.updating_selection = False

    def on_status_filter_change(self, event):
        self.filter_bookmarks()

    def on_bookmark_select(self, event):
        selected = self.bm_tree.selection()
        if not selected:
            return
            
        item_id = selected[0]
        # Get details from DB
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, folder, category, status_code, is_valid, last_checked FROM bookmarks WHERE id = ?", (item_id,))
        r = cursor.fetchone()
        conn.close()
        
        if r:
            self.lbl_det_title.configure(text=f"标题: {r['title']}")
            self.lbl_det_url.configure(text=f"网址: {r['url']}")
            self.lbl_det_folder.configure(text=f"文件夹: {r['folder']}")
            self.lbl_det_cat.configure(text=f"分类: {r['category']}")
            
            is_valid = r['is_valid']
            status_text = "未检测"
            if is_valid == 1:
                status_text = f"有效 ({r['status_code']})"
            elif is_valid == 0:
                code = r['status_code']
                if code == -1:
                    status_text = "超时"
                elif code == -2:
                    status_text = "协议不支持"
                elif code == -9:
                    status_text = "网络连接失败 / DNS解析错误 / SSL证书错误"
                else:
                    status_text = f"失效 ({code})"
                    
            self.lbl_det_status.configure(text=f"HTTP状态: {status_text}")
            self.lbl_det_time.configure(text=f"最后检测: {r['last_checked'] or '-'}")

    def on_bookmark_double_click(self, event):
        selected = self.bm_tree.selection()
        if selected:
            item_id = selected[0]
            conn = database.get_db_connection(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT url FROM bookmarks WHERE id = ?", (item_id,))
            url = cursor.fetchone()['url']
            conn.close()
            webbrowser.open(url)

    def sort_treeview(self, col, reverse):
        """
        Sort treeview column values.
        """
        l = [(self.bm_tree.set(k, col), k) for k in self.bm_tree.get_children('')]
        # Check if the column represents a date or status to sort intelligently
        l.sort(reverse=reverse)
        
        # Rearrange items
        for index, (val, k) in enumerate(l):
            self.bm_tree.move(k, '', index)
            
        # Reverse sort next time
        self.bm_tree.heading(col, command=lambda: self.sort_treeview(col, not reverse))

    # ==================== ACTIONS AND OPERATIONS ====================
    def import_bookmarks(self):
        file_path = filedialog.askopenfilename(
            title="选择导出的书签 HTML 文件",
            filetypes=[("HTML Files", "*.html;*.htm"), ("All Files", "*.*")]
        )
        if not file_path:
            return
            
        try:
            self.lbl_status.configure(text="正在解析书签 HTML 文件...")
            bookmarks, folders = bookmark_parser.parse_bookmarks_html(file_path)
            
            if not bookmarks:
                messagebox.showwarning("导入提示", "未在该文件中解析到任何有效的书签链接！")
                self.lbl_status.configure(text="导入失败")
                return
                
            # Clear current bookmarks and import new ones
            conn = database.get_db_connection(DB_PATH)
            database.clear_all_bookmarks(conn)
            
            cursor = conn.cursor()
            
            # Save folders
            for folder in folders:
                cursor.execute("INSERT INTO folders (name, parent_id, level) VALUES (?, 0, 0)", (folder,))
                
            # Save bookmarks
            for bm in bookmarks:
                cursor.execute(
                    """
                    INSERT INTO bookmarks (url, title, folder, add_date, hash, is_valid)
                    VALUES (?, ?, ?, ?, ?, -1)
                    """,
                    (bm['url'], bm['title'], bm['folder'], bm['add_date'], bm['hash'])
                )
                
            # Log import history
            import_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO import_history (file_path, import_time, bookmark_count) VALUES (?, ?, ?)",
                (file_path, import_time, len(bookmarks))
            )
            
            # Save initial snapshot Version 0
            database.save_version_snapshot(conn, "初始导入书签")
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("导入成功", f"成功导入 {len(bookmarks)} 条书签，并成功建立初始备份快照！")
            self.load_data_dashboard()
        except Exception as e:
            messagebox.showerror("导入错误", f"解析或保存书签时出错：\n{str(e)}")
            self.lbl_status.configure(text="导入出错")

    def export_bookmarks(self):
        # Fetch current list of bookmarks from DB
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, folder, category, add_date FROM bookmarks")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            messagebox.showwarning("导出提示", "当前数据库中无书签数据！")
            return
            
        bookmarks = [dict(r) for r in rows]
        
        file_path = filedialog.asksaveasfilename(
            title="选择导出位置",
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html")]
        )
        if not file_path:
            return
            
        try:
            bookmark_parser.export_bookmarks_to_html(bookmarks, file_path)
            messagebox.showinfo("导出成功", f"成功导出 {len(bookmarks)} 个书签到本地：\n{file_path}")
        except Exception as e:
            messagebox.showerror("导出错误", f"导出失败：\n{str(e)}")

    def run_deduplicate(self):
        # Check current duplicate count
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as dup_cnt FROM bookmarks WHERE hash IN (SELECT hash FROM bookmarks GROUP BY hash HAVING COUNT(*) > 1)")
        duplicates = cursor.fetchone()['dup_cnt']
        conn.close()
        
        if duplicates == 0:
            messagebox.showinfo("去重整理", "当前没有重复的网址书签！")
            return
            
        # Open custom decision dialog
        DuplicateBookmarksDialog(self.root, DB_PATH, self.load_data_dashboard)

    def delete_invalid(self):
        if not self.checked_bookmark_ids:
            messagebox.showinfo("删除提示", "您目前没有勾选任何书签！请先在列表中勾选要删除的失效书签（🔴）。")
            return
            
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        
        # We query only bookmarks that are checked and also invalid (is_valid = 0)
        placeholders = ",".join("?" for _ in self.checked_bookmark_ids)
        cursor.execute(
            f"SELECT id, title FROM bookmarks WHERE id IN ({placeholders}) AND is_valid = 0",
            list(self.checked_bookmark_ids)
        )
        invalid_checked = cursor.fetchall()
        conn.close()
        
        if not invalid_checked:
            messagebox.showinfo("删除提示", "在您勾选的书签中，没有检测到已失效的书签（🔴）！\n请注意，未检测或有效的书签无法通过本功能删除。")
            return
            
        confirm = messagebox.askyesno(
            "确认删除",
            f"您确定要删除选中的 {len(invalid_checked)} 个已失效的书签吗？（此操作可以撤销）"
        )
        if not confirm:
            return
            
        conn = database.get_db_connection(DB_PATH)
        try:
            # Save version snapshot before deleting
            database.save_version_snapshot(conn, "删除选中失效书签")
            cursor = conn.cursor()
            for r in invalid_checked:
                cursor.execute("DELETE FROM bookmarks WHERE id = ?", (r['id'],))
                self.checked_bookmark_ids.discard(str(r['id']))
            conn.commit()
            
            messagebox.showinfo("清理成功", f"已成功删除 {len(invalid_checked)} 条失效书签！")
            self.load_data_dashboard()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("清理失败", f"删除失效书签时出错：\n{str(e)}")
        finally:
            conn.close()

    def run_ai_classify(self):
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM bookmarks")
        total = cursor.fetchone()['cnt']
        conn.close()
        
        if total == 0:
            messagebox.showwarning("分类提示", "当前无书签数据！")
            return
            
        # Run in a small thread so UI doesn't freeze
        def bg_classify():
            self.lbl_status.configure(text="正在载入离线规则库，执行AI分类中...")
            self.progress.pack(side=RIGHT, padx=10)
            self.progress.configure(mode='indeterminate')
            self.progress.start()
            
            try:
                count = classifier.run_ai_classification(DB_PATH, "rules.json")
                self.root.after(0, lambda: self.finish_classify(count))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("分类错误", f"分类失败：\n{str(e)}"))
                self.root.after(0, self.cleanup_progress)
                
        t = threading.Thread(target=bg_classify, daemon=True)
        t.start()

    def finish_classify(self, count):
        self.cleanup_progress()
        messagebox.showinfo("分类完成", f"AI分类引擎已成功处理 {count} 个书签的分类匹配！")
        self.load_data_dashboard()

    # ==================== THREADED BOOKMARKS CHECKER ====================
    def start_validity_check(self):
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM bookmarks")
        total = cursor.fetchone()['cnt']
        conn.close()
        
        if total == 0:
            messagebox.showwarning("检测提示", "当前无书签数据！")
            return
            
        self.check_cancelled = False
        self.btn_check.configure(state=DISABLED)
        self.btn_cancel.pack(side=RIGHT, padx=5)
        self.progress.pack(side=RIGHT, padx=10)
        self.progress.configure(mode='determinate')
        self.progress['value'] = 0
        
        self.lbl_status.configure(text="开始检测网址有效性...")
        
        def run_check():
            try:
                bookmark_processor.check_all_bookmarks_validity(
                    DB_PATH,
                    progress_callback=self.update_check_progress,
                    check_cancelled=lambda: self.check_cancelled
                )
                self.root.after(0, self.finish_validity_check)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("检测错误", f"检测过程中断：\n{str(e)}"))
                self.root.after(0, self.finish_validity_check)
                
        self.check_thread = threading.Thread(target=run_check, daemon=True)
        self.check_thread.start()

    def update_check_progress(self, completed, total):
        pct = int((completed / total) * 100)
        self.root.after(0, lambda: self.set_progress_values(completed, total, pct))

    def set_progress_values(self, completed, total, pct):
        self.progress['value'] = pct
        self.lbl_status.configure(text=f"网址检测中... 已完成 {completed}/{total} ({pct}%)")

    def cancel_validity_check(self):
        self.check_cancelled = True
        self.lbl_status.configure(text="正在取消检测，请稍候...")
        self.btn_cancel.configure(state=DISABLED)

    def finish_validity_check(self):
        self.cleanup_progress()
        self.btn_check.configure(state=NORMAL)
        self.btn_cancel.configure(state=NORMAL)
        self.btn_cancel.pack_forget()
        
        if self.check_cancelled:
            messagebox.showinfo("检测中断", "网址有效性检测已被用户手动中止。")
        else:
            messagebox.showinfo("检测完成", "网址有效性一键检测全部完成！")
            
        self.load_data_dashboard()

    def cleanup_progress(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.lbl_status.configure(text="系统就绪")

    # ==================== UNDO / RESTORE LOGIC ====================
    def undo_operation(self):
        conn = database.get_db_connection(DB_PATH)
        latest_ver, action_type, _ = database.get_latest_version(conn)
        
        if latest_ver <= 0:
            messagebox.showinfo("撤销提示", "当前已是初始状态，无法继续撤销！")
            conn.close()
            return
            
        confirm = messagebox.askyesno(
            "撤销确认",
            f"您确定要撤销上一步操作【{action_type}】吗？数据将被恢复到该操作之前的版本。"
        )
        if not confirm:
            conn.close()
            return
            
        target_ver = latest_ver - 1
        success = database.rollback_to_version(conn, target_ver)
        conn.close()
        
        if success:
            messagebox.showinfo("撤销成功", "已成功恢复到上一个版本的状态！")
            self.load_data_dashboard()
        else:
            messagebox.showerror("撤销失败", "无法恢复到上一个版本的快照！")

    def restore_initial(self):
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM bookmarks_version WHERE version = 0")
        has_initial = cursor.fetchone()['cnt'] > 0
        conn.close()
        
        if not has_initial:
            messagebox.showinfo("还原提示", "未找到初始备份版本！")
            return
            
        confirm = messagebox.askyesno(
            "还原确认",
            "您确定要还原到【初始导入状态】吗？\n\n这将清空您导入之后做过的所有去重、分类、删除操作！"
        )
        if not confirm:
            return
            
        conn = database.get_db_connection(DB_PATH)
        success = database.rollback_to_version(conn, 0)
        conn.close()
        
        if success:
            messagebox.showinfo("还原成功", "书签已恢复至初始导入状态！")
            self.load_data_dashboard()
        else:
            messagebox.showerror("还原失败", "无法还原到初始状态快照！")

    def clear_database(self):
        confirm = messagebox.askyesno(
            "清空确认",
            "您确定要清空软件中已导入的所有书签数据及备份历史吗？\n\n注意：此操作仅清空本软件的本地数据库，绝对不会损坏或修改您在本地硬盘上的原始书签 HTML 文件。"
        )
        if not confirm:
            return
            
        try:
            conn = database.get_db_connection(DB_PATH)
            database.clear_all_bookmarks(conn)
            conn.close()
            
            self.checked_bookmark_ids.clear()
            self.current_folder = "All"
            self.current_category = "All"
            
            messagebox.showinfo("清空成功", "所有书签数据及历史记录已成功清除！您现在可以导入新的书签文件。")
            self.load_data_dashboard()
        except Exception as e:
            messagebox.showerror("清空失败", f"清除数据时出错：\n{str(e)}")

    # ==================== CONTEXT MENU ACTIONS ====================
    def show_context_menu(self, event):
        item_id = self.bm_tree.identify_row(event.y)
        if item_id:
            # Add item to selection if not selected
            if item_id not in self.bm_tree.selection():
                self.bm_tree.selection_set(item_id)
            self.context_menu.post(event.x_root, event.y_root)

    def open_selected_in_browser(self):
        selected = self.bm_tree.selection()
        for iid in selected:
            conn = database.get_db_connection(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT url FROM bookmarks WHERE id = ?", (iid,))
            row = cursor.fetchone()
            conn.close()
            if row:
                webbrowser.open(row['url'])

    def edit_selected_bookmark(self):
        selected = self.bm_tree.selection()
        if not selected:
            return
        iid = selected[0]
        
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title, url FROM bookmarks WHERE id = ?", (iid,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return
            
        # Edit dialog
        new_title = simpledialog.askstring("编辑标题", "请输入新的书签标题:", initialvalue=row['title'])
        if new_title is None:
            return
            
        new_url = simpledialog.askstring("编辑网址", "请输入新的书签网址:", initialvalue=row['url'])
        if new_url is None:
            return
            
        # Update database with snapshot
        conn = database.get_db_connection(DB_PATH)
        try:
            database.save_version_snapshot(conn, "手动编辑书签")
            cursor = conn.cursor()
            url_hash = hashlib.md5(new_url.encode('utf-8', errors='ignore')).hexdigest()
            cursor.execute(
                "UPDATE bookmarks SET title = ?, url = ?, hash = ? WHERE id = ?",
                (new_title, new_url, url_hash, iid)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("修改失败", str(e))
        finally:
            conn.close()
            
        self.load_data_dashboard()

    def delete_selected_bookmark(self):
        selected = self.bm_tree.selection()
        if not selected:
            return
            
        confirm = messagebox.askyesno("删除确认", f"确定要删除选中的 {len(selected)} 个书签吗？")
        if not confirm:
            return
            
        conn = database.get_db_connection(DB_PATH)
        try:
            database.save_version_snapshot(conn, "手动删除书签")
            cursor = conn.cursor()
            for iid in selected:
                cursor.execute("DELETE FROM bookmarks WHERE id = ?", (iid,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("删除失败", str(e))
        finally:
            conn.close()
            
        self.load_data_dashboard()

    def manual_classify_bookmark(self):
        selected = self.bm_tree.selection()
        if not selected:
            return
            
        # Get list of categories from DB
        conn = database.get_db_connection(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM bookmarks")
        cats = [r['category'] for r in cursor.fetchall() if r['category']]
        conn.close()
        
        if "📦 其他" not in cats:
            cats.append("📦 其他")
            
        # Ask user for category
        choice = simpledialog.askstring(
            "选择分类",
            f"请输入要划分到的分类名称。\n\n已知分类有:\n" + ", ".join(cats)
        )
        
        if not choice:
            return
            
        conn = database.get_db_connection(DB_PATH)
        try:
            database.save_version_snapshot(conn, "手动修改分类")
            cursor = conn.cursor()
            for iid in selected:
                cursor.execute("UPDATE bookmarks SET category = ? WHERE id = ?", (choice.strip(), iid))
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("分类失败", str(e))
        finally:
            conn.close()
            
        self.load_data_dashboard()

    def on_tree_click(self, event):
        region = self.bm_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.bm_tree.identify_column(event.x)
            if column == "#1":  # Column 1 is the 'select' column
                item_id = self.bm_tree.identify_row(event.y)
                if item_id:
                    self.toggle_bookmark_select(item_id)
                    return "break"

    def toggle_bookmark_select(self, item_id):
        if item_id in self.checked_bookmark_ids:
            self.checked_bookmark_ids.remove(item_id)
        else:
            self.checked_bookmark_ids.add(item_id)
        self.filter_bookmarks()

    def toggle_select_all(self):
        is_checked = self.var_select_all.get()
        visible_items = self.bm_tree.get_children()
        for item_id in visible_items:
            if is_checked:
                self.checked_bookmark_ids.add(item_id)
            else:
                self.checked_bookmark_ids.discard(item_id)
        self.filter_bookmarks()


class DuplicateBookmarksDialog(tb.Toplevel):
    def __init__(self, parent, db_path, on_success_callback):
        super().__init__(parent)
        self.title("重复书签明细与决策")
        self.geometry("950x700")
        self.transient(parent)
        self.parent = parent
        self.db_path = db_path
        self.on_success = on_success_callback
        
        self.grab_set()
        
        self.build_ui()
        self.load_duplicates()
        
    def build_ui(self):
        # Header Label
        tb.Label(self, text="以下为数据库中的重复书签链接（按网址分组，不同分组交替背景色）：", font=("Microsoft YaHei", 10, "bold"), padding=10).pack(anchor=W)
        
        # Grid Container
        grid_frame = tb.Frame(self, padding=10)
        grid_frame.pack(fill=BOTH, expand=YES)
        
        columns = ("title", "url", "folder", "add_date")
        self.tree = ttk.Treeview(grid_frame, columns=columns, show="headings", height=8)
        
        self.tree.heading("title", text="标题")
        self.tree.heading("url", text="网址")
        self.tree.heading("folder", text="所处文件夹")
        self.tree.heading("add_date", text="导入/添加时间")
        
        self.tree.column("title", width=250, anchor=W)
        self.tree.column("url", width=350, anchor=W)
        self.tree.column("folder", width=150, anchor=W)
        self.tree.column("add_date", width=150, anchor=CENTER)
        
        self.tree.pack(fill=BOTH, expand=YES, side=LEFT)
        
        scroll = tb.Scrollbar(grid_frame, orient=VERTICAL, command=self.tree.yview)
        scroll.pack(fill=Y, side=RIGHT)
        self.tree.configure(yscrollcommand=scroll.set)
        
        # Tag styling for group separation
        self.tree.tag_configure("group_a", background="#1a1c23")
        self.tree.tag_configure("group_b", background="#2a2e39")
        
        # Strategy Frame
        strat_frame = tb.LabelFrame(self, text="去重决策策略")
        strat_frame.pack(fill=X, padx=10, pady=10)
        
        strat_inner = tb.Frame(strat_frame, padding=15)
        strat_inner.pack(fill=BOTH, expand=YES)
        
        self.strat_var = tk.StringVar(value="oldest")
        
        tb.Radiobutton(
            strat_inner, 
            text="保留最早添加的书签（保留创建时间最早或数据库中ID最小的那一条记录，其余副本移去）", 
            variable=self.strat_var, 
            value="oldest",
            bootstyle="primary"
        ).pack(anchor=W, pady=5)
        
        tb.Radiobutton(
            strat_inner, 
            text="保留最新添加的书签（保留创建时间最晚或数据库中ID最大的那一条记录，其余副本移去）", 
            variable=self.strat_var, 
            value="latest",
            bootstyle="primary"
        ).pack(anchor=W, pady=5)
        
        # Bottom Buttons
        btn_frame = tb.Frame(self, padding=10)
        btn_frame.pack(fill=X, side=BOTTOM)
        
        btn_cancel = tb.Button(btn_frame, text="取消", bootstyle="secondary-outline", width=10, command=self.destroy)
        btn_cancel.pack(side=RIGHT, padx=5)
        
        btn_confirm = tb.Button(btn_frame, text="立即执行去重", bootstyle="success", width=15, command=self.execute_dedup)
        btn_confirm.pack(side=RIGHT, padx=5)

    def load_duplicates(self):
        conn = database.get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        # Fetch duplicate rows grouped together by hash
        cursor.execute(
            """
            SELECT id, url, title, folder, add_date, hash FROM bookmarks
            WHERE hash IN (SELECT hash FROM bookmarks GROUP BY hash HAVING COUNT(*) > 1)
            ORDER BY hash ASC, id ASC
            """
        )
        rows = cursor.fetchall()
        conn.close()
        
        last_hash = ""
        use_group_a = True
        
        for r in rows:
            curr_hash = r['hash']
            if last_hash and curr_hash != last_hash:
                use_group_a = not use_group_a
            last_hash = curr_hash
            
            tag = "group_a" if use_group_a else "group_b"
            
            self.tree.insert(
                "",
                "end",
                iid=str(r['id']),
                values=(r['title'], r['url'], r['folder'], r['add_date']),
                tags=(tag,)
            )

    def execute_dedup(self):
        strategy = self.strat_var.get()
        try:
            deleted_count = bookmark_processor.deduplicate_bookmarks(self.db_path, keep_strategy=strategy)
            messagebox.showinfo("去重成功", f"成功删除 {deleted_count} 个重复链接，且原始网址数据已安全备份！")
            self.on_success()
            self.destroy()
        except Exception as e:
            messagebox.showerror("去重失败", f"去重整理出错：\n{str(e)}")
            self.destroy()
