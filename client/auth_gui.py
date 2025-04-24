import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
import os
from auth_client import AuthClient

class AuthGUI:
    """用户认证界面，包含登录和注册功能"""

    def __init__(self, root, auth_success_callback=None):
        """初始化认证界面
        
        Args:
            root: Tkinter根窗口
            auth_success_callback: 认证成功后的回调函数
        """
        self.root = root
        self.auth_success_callback = auth_success_callback
        self.auth_client = AuthClient()
        
        self.root.title("工作监控系统 - 用户认证")
        # 增加窗口高度，确保所有控件都能显示
        self.root.geometry("400x550")
        self.root.resizable(False, False)
        
        self._create_widgets()
        self._center_window()
        
        # 检查是否已有保存的令牌
        if self.auth_client.is_authenticated():
            username = self.auth_client.get_username()
            messagebox.showinfo("欢迎回来", f"欢迎回来，{username}")
            if self.auth_success_callback:
                self.auth_success_callback(self.auth_client)
                
    def _center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
    def _create_widgets(self):
        """创建GUI控件"""
        # 设置样式
        style = ttk.Style()
        style.configure('TLabel', font=('微软雅黑', 12))
        style.configure('TButton', font=('微软雅黑', 12))
        style.configure('TEntry', font=('微软雅黑', 12))
        style.configure('Header.TLabel', font=('微软雅黑', 16, 'bold'))
        style.configure('Register.TButton', background='#4CAF50', foreground='white')
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title_label = ttk.Label(main_frame, text="工作监控系统", style='Header.TLabel')
        title_label.pack(pady=10)
        
        subtitle_label = ttk.Label(main_frame, text="请登录或注册账号")
        subtitle_label.pack(pady=5)
        
        # 创建选项卡
        tab_control = ttk.Notebook(main_frame)
        tab_control.pack(fill=tk.BOTH, expand=1, pady=20)
        
        # 登录选项卡
        login_tab = ttk.Frame(tab_control)
        tab_control.add(login_tab, text="登录")
        
        # 注册选项卡
        register_tab = ttk.Frame(tab_control)
        tab_control.add(register_tab, text="注册")
        
        # 登录表单
        login_form = ttk.Frame(login_tab, padding=20)
        login_form.pack(fill=tk.BOTH, expand=True)
        
        # 用户名
        login_username_label = ttk.Label(login_form, text="用户名:")
        login_username_label.pack(fill=tk.X, pady=5)
        
        self.login_username_var = tk.StringVar()
        login_username_entry = ttk.Entry(login_form, textvariable=self.login_username_var, width=30)
        login_username_entry.pack(fill=tk.X, pady=5)
        
        # 密码
        login_password_label = ttk.Label(login_form, text="密码:")
        login_password_label.pack(fill=tk.X, pady=5)
        
        self.login_password_var = tk.StringVar()
        login_password_entry = ttk.Entry(login_form, textvariable=self.login_password_var, show="*", width=30)
        login_password_entry.pack(fill=tk.X, pady=5)
        
        # 登录按钮
        login_btn_frame = ttk.Frame(login_form)
        login_btn_frame.pack(fill=tk.X, pady=20)
        
        self.login_btn = ttk.Button(login_btn_frame, text="登录", command=self.login)
        self.login_btn.pack(fill=tk.X)
        
        # 注册表单
        register_form = ttk.Frame(register_tab, padding=20)
        register_form.pack(fill=tk.BOTH, expand=True)
        
        # 用户名
        register_username_label = ttk.Label(register_form, text="用户名:")
        register_username_label.pack(fill=tk.X, pady=5)
        
        self.register_username_var = tk.StringVar()
        register_username_entry = ttk.Entry(register_form, textvariable=self.register_username_var, width=30)
        register_username_entry.pack(fill=tk.X, pady=5)
        
        # 密码
        register_password_label = ttk.Label(register_form, text="密码:")
        register_password_label.pack(fill=tk.X, pady=5)
        
        self.register_password_var = tk.StringVar()
        register_password_entry = ttk.Entry(register_form, textvariable=self.register_password_var, show="*", width=30)
        register_password_entry.pack(fill=tk.X, pady=5)
        
        # 确认密码
        confirm_password_label = ttk.Label(register_form, text="确认密码:")
        confirm_password_label.pack(fill=tk.X, pady=5)
        
        self.confirm_password_var = tk.StringVar()
        confirm_password_entry = ttk.Entry(register_form, textvariable=self.confirm_password_var, show="*", width=30)
        confirm_password_entry.pack(fill=tk.X, pady=5)
        
        # 注册按钮 - 优化显示
        register_btn_frame = ttk.Frame(register_form)
        register_btn_frame.pack(fill=tk.X, pady=20)
        
        # 使用标准tk按钮以获得更好的可见性
        self.register_btn = tk.Button(
            register_btn_frame, 
            text="注册", 
            command=self.register, 
            bg="#4CAF50", 
            fg="white",
            font=('微软雅黑', 12),
            padx=20,
            pady=8,
            relief=tk.RAISED,
            cursor="hand2"
        )
        self.register_btn.pack(fill=tk.X)
        
        # 服务器设置框架
        server_frame = ttk.LabelFrame(main_frame, text="服务器设置", padding=10)
        server_frame.pack(fill=tk.X, pady=10)
        
        server_url_label = ttk.Label(server_frame, text="服务器地址:")
        server_url_label.pack(side=tk.LEFT, padx=5)
        
        self.server_url_var = tk.StringVar(value="http://localhost:5000")
        server_url_entry = ttk.Entry(server_frame, textvariable=self.server_url_var, width=25)
        server_url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 版权信息
        copyright_label = ttk.Label(main_frame, text="© 2025 工作监控系统", font=('微软雅黑', 8))
        copyright_label.pack(side=tk.BOTTOM, pady=10)
        
    def login(self):
        """用户登录"""
        username = self.login_username_var.get().strip()
        password = self.login_password_var.get().strip()
        
        if not username or not password:
            messagebox.showerror("错误", "用户名和密码不能为空")
            return
            
        # 更新服务器地址
        self.auth_client.server_url = self.server_url_var.get().strip()
        
        # 禁用按钮，避免重复点击
        self.login_btn.config(state=tk.DISABLED)
        
        # 在新线程中执行登录，避免阻塞UI
        threading.Thread(target=self._login_thread, args=(username, password), daemon=True).start()
        
    def _login_thread(self, username, password):
        """登录线程"""
        success, message = self.auth_client.login(username, password)
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._handle_login_result(success, message))
        
    def _handle_login_result(self, success, message):
        """处理登录结果"""
        # 重新启用按钮
        self.login_btn.config(state=tk.NORMAL)
        
        if success:
            messagebox.showinfo("成功", "登录成功")
            
            # 调用认证成功回调
            if self.auth_success_callback:
                self.auth_success_callback(self.auth_client)
        else:
            messagebox.showerror("错误", message)
            
    def register(self):
        """用户注册"""
        username = self.register_username_var.get().strip()
        password = self.register_password_var.get().strip()
        confirm_password = self.confirm_password_var.get().strip()
        
        if not username or not password or not confirm_password:
            messagebox.showerror("错误", "所有字段都不能为空")
            return
            
        if password != confirm_password:
            messagebox.showerror("错误", "两次输入的密码不匹配")
            return
            
        # 更新服务器地址
        self.auth_client.server_url = self.server_url_var.get().strip()
        
        # 禁用按钮，避免重复点击
        self.register_btn.config(state=tk.DISABLED)
        
        # 在新线程中执行注册，避免阻塞UI
        threading.Thread(target=self._register_thread, args=(username, password), daemon=True).start()
        
    def _register_thread(self, username, password):
        """注册线程"""
        success, message = self.auth_client.register(username, password)
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._handle_register_result(success, message, username, password))
        
    def _handle_register_result(self, success, message, username, password):
        """处理注册结果"""
        # 重新启用按钮
        self.register_btn.config(state=tk.NORMAL)
        
        if success:
            messagebox.showinfo("成功", "注册成功，现在为您登录")
            
            # 自动登录
            self._login_thread(username, password)
        else:
            messagebox.showerror("错误", message)