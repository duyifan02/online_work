import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
from monitor import MonitorSystem
import os
import webbrowser
import datetime
import json
import logging
import shutil
from auth_client import AuthClient
from auth_gui import AuthGUI

class MonitoringGUI:
    def __init__(self, root, auth_client=None):
        """初始化监控界面
        
        Args:
            root: Tkinter根窗口
            auth_client: 已认证的客户端对象
        """
        self.root = root
        self.auth_client = auth_client
        
        # 检查认证状态
        if not self.auth_client or not self.auth_client.is_authenticated():
            messagebox.showerror("错误", "请先登录")
            return
            
        self.root.title(f"线上工作打卡控制面板 - {self.auth_client.get_username()}")
        self.root.geometry("600x800")  # 增加高度以容纳周末时间显示
        self.root.resizable(False, False)
        
        # 初始化检测系统（固定30分钟间隔）
        self.monitor = MonitorSystem(interval=1800)  # 固定为30分钟(1800秒)
        self.monitor.set_status_callback(self.update_status)
        self.monitor.set_stats_callback(self.update_stats)
        
        # 项目根目录
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        
        self._create_widgets()
        self._center_window()
        
        # 注册窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 立即更新统计信息
        self.update_stats_display()
        
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
        style.configure('TButton', font=('微软雅黑', 12))
        style.configure('TLabel', font=('微软雅黑', 12))
        style.configure('Weekend.TLabel', foreground='blue')
        style.configure('Info.TLabel', foreground='gray')
        style.configure('Header.TLabel', font=('微软雅黑', 12, 'bold'))
        style.configure('Upload.TButton', foreground='blue')
        style.configure('Admin.TButton', foreground='purple')
        style.configure('Logout.TButton', foreground='red')
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title_label = ttk.Label(main_frame, text="自动检测系统", font=('微软雅黑', 16, 'bold'))
        title_label.pack(pady=10)
        
        # 添加用户信息
        user_frame = ttk.Frame(main_frame)
        user_frame.pack(fill=tk.X, pady=5)
        
        user_label = ttk.Label(user_frame, text=f"当前用户: {self.auth_client.get_username()}", font=('微软雅黑', 10))
        user_label.pack(side=tk.LEFT)
        
        # 如果是管理员，显示管理员标签
        if self.auth_client.is_admin():
            admin_label = ttk.Label(user_frame, text="[管理员]", font=('微软雅黑', 10, 'bold'), foreground='purple')
            admin_label.pack(side=tk.LEFT, padx=5)
            
            # 添加管理员面板按钮
            admin_panel_btn = ttk.Button(
                user_frame, 
                text="管理员面板", 
                command=self.open_admin_panel,
                style='Admin.TButton'
            )
            admin_panel_btn.pack(side=tk.RIGHT)
            
        # 登出按钮
        logout_btn = ttk.Button(user_frame, text="登出", command=self.logout, style='Logout.TButton')
        logout_btn.pack(side=tk.RIGHT, padx=10)
        
        # 状态框架
        status_frame = ttk.LabelFrame(main_frame, text="状态", padding="10")
        status_frame.pack(fill=tk.X, pady=10)
        
        self.status_label = ttk.Label(status_frame, text="未启动", font=('微软雅黑', 12))
        self.status_label.pack()
        
        # 添加统计信息框架
        stats_frame = ttk.LabelFrame(main_frame, text="当前使用统计", padding="10")
        stats_frame.pack(fill=tk.X, pady=10)
        
        # 今日使用时长
        today_frame = ttk.Frame(stats_frame)
        today_frame.pack(fill=tk.X, pady=5)
        
        today_label = ttk.Label(today_frame, text="今日使用时长:", width=15)
        today_label.pack(side=tk.LEFT)
        
        self.today_time_label = ttk.Label(today_frame, text="00:00:00")
        self.today_time_label.pack(side=tk.LEFT, padx=10)
        
        # 当天是否为周末指示
        self.is_weekend_label = ttk.Label(today_frame, text="", style='Weekend.TLabel')
        self.is_weekend_label.pack(side=tk.LEFT, padx=10)
        
        # 本周使用时长
        week_frame = ttk.Frame(stats_frame)
        week_frame.pack(fill=tk.X, pady=5)
        
        week_label = ttk.Label(week_frame, text="本周使用时长:", width=15)
        week_label.pack(side=tk.LEFT)
        
        self.week_time_label = ttk.Label(week_frame, text="00:00:00")
        self.week_time_label.pack(side=tk.LEFT, padx=10)
        
        # 新增：周末使用时长
        weekend_frame = ttk.Frame(stats_frame)
        weekend_frame.pack(fill=tk.X, pady=5)
        
        weekend_label = ttk.Label(weekend_frame, text="周末使用时长:", width=15, style='Weekend.TLabel')
        weekend_label.pack(side=tk.LEFT)
        
        self.weekend_time_label = ttk.Label(weekend_frame, text="00:00:00", style='Weekend.TLabel')
        self.weekend_time_label.pack(side=tk.LEFT, padx=10)
        
        # 固定间隔提示（替换原来的可编辑间隔设置）        
        interval_frame = ttk.Frame(main_frame)
        interval_frame.pack(fill=tk.X, pady=10)
        
        interval_label = ttk.Label(interval_frame, text="记录间隔:", width=15)
        interval_label.pack(side=tk.LEFT, padx=5)
        
        fixed_interval_label = ttk.Label(interval_frame, text="30分钟", style='Info.TLabel')
        fixed_interval_label.pack(side=tk.LEFT, padx=5)
        
        # 创建按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        # 开始按钮
        self.start_btn = ttk.Button(btn_frame, text="开始", command=self.start_monitoring)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        # 暂停/恢复按钮
        self.pause_btn = ttk.Button(btn_frame, text="暂停", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=10)
        
        # 停止按钮
        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # 添加上传按钮框架
        upload_frame = ttk.Frame(main_frame)
        upload_frame.pack(fill=tk.X, pady=10)
        
        # 上传按钮
        self.upload_btn = ttk.Button(
            upload_frame, 
            text="上传到服务器", 
            command=self.upload_data,
            style='Upload.TButton'
        )
        self.upload_btn.pack(fill=tk.X, padx=10, expand=True)
        
        # 上传状态标签
        self.upload_status_label = ttk.Label(upload_frame, text="未上传服务器", style='Info.TLabel')
        self.upload_status_label.pack(pady=5, fill=tk.X, expand=True)
        
        # 添加历史数据查看框架 - 只保留周统计数据
        history_frame = ttk.LabelFrame(main_frame, text="历史数据", padding="10")
        history_frame.pack(fill=tk.X, pady=10)
        
        # 周选择框架
        week_select_frame = ttk.Frame(history_frame)
        week_select_frame.pack(fill=tk.X, pady=5)
        
        week_select_label = ttk.Label(week_select_frame, text="选择周:", width=15)
        week_select_label.pack(side=tk.LEFT)
        
        # 获取可用周列表
        available_weeks = self.monitor.get_available_weeks()
        week_display_values = [f"{w['week_start_str']} 开始" for w in available_weeks] if available_weeks else ["无数据"]
        
        self.week_var = tk.StringVar(value=week_display_values[0] if week_display_values else "无数据")
        self.week_combo = ttk.Combobox(week_select_frame, textvariable=self.week_var, 
                                      values=week_display_values, 
                                      state="readonly", 
                                      width=20)
        self.week_combo.pack(side=tk.LEFT, padx=5)
        
        # 查看周统计按钮
        view_week_btn = ttk.Button(week_select_frame, text="查看周数据", command=self.view_week_stats)
        view_week_btn.pack(side=tk.LEFT, padx=10)
        
        # 周统计显示框架
        self.week_stats_frame = ttk.Frame(history_frame)
        self.week_stats_frame.pack(fill=tk.BOTH, pady=10, expand=True)
        
        # 存储周数据备用
        self.available_weeks = available_weeks
        
        # 初始更新周统计显示
        if available_weeks:
            self.update_week_stats_display(available_weeks[0])
            
    def upload_data(self):
        """将数据上传到服务器"""
        # 禁用上传按钮，避免重复点击
        self.upload_btn.config(state=tk.DISABLED)
        self.upload_status_label.config(text="上传中...", foreground="blue")
        
        # 创建上传线程
        upload_thread = threading.Thread(target=self._upload_thread)
        upload_thread.daemon = True
        upload_thread.start()
        
    def _upload_thread(self):
        """在线程中执行上传，避免阻塞UI"""
        try:
            # 确保在上传前保存最新统计数据
            if hasattr(self, 'monitor') and self.monitor:
                self.monitor.save_stats()
                
            # 上传周统计数据
            self.root.after(0, lambda: self.upload_status_label.config(
                text="正在上传周统计数据...",
                foreground="blue"
            ))
            
            # 获取当前周的加密统计文件 (.enc)
            current_week_enc_file = self.monitor.current_week_file
            
            # 创建临时文件用于上传
            temp_stats_file = None
            
            # 如果加密文件存在，解密并创建临时JSON文件用于上传
            if os.path.exists(current_week_enc_file):
                try:
                    stats_data = self.monitor.decrypt_file(current_week_enc_file)
                    if stats_data:
                        temp_dir = os.path.join(self.monitor.SAVE_DIR, "temp_upload")
                        if not os.path.exists(temp_dir):
                            os.makedirs(temp_dir)
                            
                        temp_stats_file = os.path.join(temp_dir, f"temp_weekly_stats.json")
                        with open(temp_stats_file, 'w', encoding='utf-8') as f:
                            json.dump(stats_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logging.error(f"解密统计文件出错: {e}")
            
            # 上传临时统计文件
            if temp_stats_file and os.path.exists(temp_stats_file):
                success, message, _ = self.auth_client.upload_weekly_stats(temp_stats_file)
                
                # 删除临时文件
                try:
                    os.remove(temp_stats_file)
                except:
                    pass
                
                if not success:
                    self.root.after(0, lambda: self.upload_status_label.config(
                        text=f"周统计数据上传失败: {message}",
                        foreground="red"
                    ))
                    # 删除临时目录并返回
                    try:
                        shutil.rmtree(os.path.dirname(temp_stats_file))
                    except:
                        pass
                    return
                else:
                    self.root.after(0, lambda: self.upload_status_label.config(
                        text="周统计数据上传成功，正在上传图像...",
                        foreground="blue"
                    ))
            else:
                self.root.after(0, lambda: self.upload_status_label.config(
                    text="未找到周统计数据，继续上传图像...",
                    foreground="blue"
                ))
            
            # 创建临时目录用于解密文件
            temp_dir = os.path.join(self.monitor.SAVE_DIR, "temp_upload")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            # 上传records目录中的记录
            uploaded_files = 0
            failed_uploads = 0
            
            # 遍历记录目录
            for week_dir_name in os.listdir(self.monitor.RECORDS_DIR):
                week_dir_path = os.path.join(self.monitor.RECORDS_DIR, week_dir_name)
                if os.path.isdir(week_dir_path):
                    # 遍历该周目录下的所有时间戳目录
                    for timestamp_dir_name in os.listdir(week_dir_path):
                        timestamp_dir_path = os.path.join(week_dir_path, timestamp_dir_name)
                        if os.path.isdir(timestamp_dir_path):
                            # 清理临时文件
                            for temp_file in os.listdir(temp_dir):
                                try:
                                    os.remove(os.path.join(temp_dir, temp_file))
                                except:
                                    pass

                            # 上传截图（一定是加密文件）
                            screenshot_enc_path = os.path.join(timestamp_dir_path, "screenshot.enc")
                            temp_screenshot_path = None
                            
                            # 解密截图并保存为临时文件
                            if os.path.exists(screenshot_enc_path):
                                try:
                                    screenshot_img = self.monitor.decrypt_image(screenshot_enc_path)
                                    if screenshot_img:
                                        temp_screenshot_path = os.path.join(temp_dir, f"{timestamp_dir_name}_screenshot.png")
                                        screenshot_img.save(temp_screenshot_path, format="PNG")
                                except Exception as e:
                                    logging.error(f"解密截图出错: {e}")
                            
                            # 上传解密后的截图
                            if temp_screenshot_path and os.path.exists(temp_screenshot_path):
                                success, message, file_path = self.auth_client.upload_file(temp_screenshot_path, "screenshot")
                                if success:
                                    uploaded_files += 1
                                else:
                                    failed_uploads += 1
                            
                            # 上传摄像头图像（一定是加密文件）
                            camera_enc_path = os.path.join(timestamp_dir_path, "camera.enc")
                            temp_camera_path = None
                            
                            # 解密摄像头图像并保存为临时文件
                            if os.path.exists(camera_enc_path):
                                try:
                                    camera_img = self.monitor.decrypt_image(camera_enc_path, "WebP")
                                    if camera_img:
                                        temp_camera_path = os.path.join(temp_dir, f"{timestamp_dir_name}_camera.webp")
                                        camera_img.save(temp_camera_path, format="WebP")
                                except Exception as e:
                                    logging.error(f"解密摄像头图片出错: {e}")
                            
                            # 上传解密后的摄像头图像
                            if temp_camera_path and os.path.exists(temp_camera_path):
                                success, message, file_path = self.auth_client.upload_file(temp_camera_path, "camera")
                                if success:
                                    uploaded_files += 1
                                else:
                                    failed_uploads += 1
                                    
                            # 上传信息文件（一定是加密文件）
                            info_enc_path = os.path.join(timestamp_dir_path, "info.enc")
                            temp_info_path = None
                            
                            # 解密信息文件并保存为临时文件
                            if os.path.exists(info_enc_path):
                                try:
                                    info_data = self.monitor.decrypt_file(info_enc_path)
                                    if info_data:
                                        temp_info_path = os.path.join(temp_dir, f"{timestamp_dir_name}_info.json")
                                        with open(temp_info_path, 'w', encoding='utf-8') as f:
                                            json.dump(info_data, f, ensure_ascii=False, indent=2)
                                except Exception as e:
                                    logging.error(f"解密信息文件出错: {e}")
                            
                            # 上传解密后的信息文件
                            if temp_info_path and os.path.exists(temp_info_path):
                                success, message, file_path = self.auth_client.upload_file(temp_info_path, "info")
                                if success:
                                    uploaded_files += 1
                                else:
                                    failed_uploads += 1
            
            # 清理临时目录
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
            
            # 更新UI
            if failed_uploads > 0:
                self.root.after(0, lambda: self.upload_status_label.config(
                    text=f"成功上传 {uploaded_files} 个文件，{failed_uploads} 个文件上传失败",
                    foreground="orange"
                ))
            else:
                self.root.after(0, lambda: self.upload_status_label.config(
                    text=f"成功上传 {uploaded_files} 个文件",
                    foreground="green"
                ))
        except Exception as e:
            self.root.after(0, lambda: self.upload_status_label.config(
                text=f"上传错误: {str(e)}",
                foreground="red"
            ))
        finally:
            # 重新启用上传按钮
            self.root.after(0, lambda: self.upload_btn.config(state=tk.NORMAL))
            
    def logout(self):
        """用户登出"""
        if messagebox.askokcancel("登出", "确定要登出吗？"):
            if self.monitor.running:
                self.monitor.stop()
            self.auth_client.logout()
            self.root.destroy()

    def open_admin_panel(self):
        """打开管理员面板"""
        if not self.auth_client.is_admin():
            messagebox.showerror("错误", "需要管理员权限")
            return
            
        # 创建新窗口
        admin_window = tk.Toplevel(self.root)
        admin_window.title("工作监控系统 - 管理员面板")
        admin_window.geometry("800x600")
        admin_window.resizable(False, False)
        
        # 在新窗口中创建管理员面板
        AdminPanel(admin_window, self.auth_client)
            
    def view_week_stats(self):
        """查看所选周的统计数据"""
        selected_index = self.week_combo.current()
        if selected_index < 0 or not self.available_weeks:
            messagebox.showinfo("提示", "没有可用的周统计数据")
            return
            
        week_info = self.available_weeks[selected_index]
        self.update_week_stats_display(week_info)
        
    def update_week_stats_display(self, week_info):
        """更新周统计数据显示"""
        # 清除现有的显示
        for widget in self.week_stats_frame.winfo_children():
            widget.destroy()
            
        # 创建周统计显示
        header_frame = ttk.Frame(self.week_stats_frame)
        header_frame.pack(fill=tk.X, pady=5)
        
        week_header = ttk.Label(header_frame, text=f"周统计: {week_info['week_start_str']} 开始", style='Header.TLabel')
        week_header.pack(pady=5)
        
        # 周使用时长
        week_time_frame = ttk.Frame(self.week_stats_frame)
        week_time_frame.pack(fill=tk.X, pady=2)
        
        week_time_label = ttk.Label(week_time_frame, text="总使用时长:", width=15)
        week_time_label.pack(side=tk.LEFT)
        
        week_time_value = ttk.Label(week_time_frame, text=week_info['week'])
        week_time_value.pack(side=tk.LEFT, padx=10)
        
        # 周末使用时长
        weekend_time_frame = ttk.Frame(self.week_stats_frame)
        weekend_time_frame.pack(fill=tk.X, pady=2)
        
        weekend_time_label = ttk.Label(weekend_time_frame, text="周末使用时长:", width=15, style='Weekend.TLabel')
        weekend_time_label.pack(side=tk.LEFT)
        
        weekend_time_value = ttk.Label(weekend_time_frame, text=week_info['weekend'], style='Weekend.TLabel')
        weekend_time_value.pack(side=tk.LEFT, padx=10)
        
        # 工作日使用时长
        weekday_seconds = week_info['week_seconds'] - week_info['weekend_seconds']
        weekday_time = self.monitor.format_time(weekday_seconds)
        
        weekday_time_frame = ttk.Frame(self.week_stats_frame)
        weekday_time_frame.pack(fill=tk.X, pady=2)
        
        weekday_time_label = ttk.Label(weekday_time_frame, text="工作日使用时长:", width=15)
        weekday_time_label.pack(side=tk.LEFT)
        
        weekday_time_value = ttk.Label(weekday_time_frame, text=weekday_time)
        weekday_time_value.pack(side=tk.LEFT, padx=10)
        
        # 日均使用时长
        avg_daily_seconds = week_info['week_seconds'] / 7
        avg_daily_time = self.monitor.format_time(avg_daily_seconds)
        
        avg_time_frame = ttk.Frame(self.week_stats_frame)
        avg_time_frame.pack(fill=tk.X, pady=2)
        
        avg_time_label = ttk.Label(avg_time_frame, text="日均使用时长:", width=15)
        avg_time_label.pack(side=tk.LEFT)
        
        avg_time_value = ttk.Label(avg_time_frame, text=avg_daily_time)
        avg_time_value.pack(side=tk.LEFT, padx=10)
        
    def update_status(self, status_text):
        """更新状态显示"""
        # 确保在主线程中更新GUI
        self.root.after(0, lambda: self.status_label.config(text=status_text))
        
    def update_stats(self, today_time, week_time, weekend_time):
        """更新统计信息显示 - 添加周末时间参数"""
        # 确保在主线程中更新GUI
        self.root.after(0, lambda: self._update_stats_labels(today_time, week_time, weekend_time))
        
    def _update_stats_labels(self, today_time, week_time, weekend_time):
        """更新统计信息标签 - 添加周末时间显示"""
        self.today_time_label.config(text=today_time)
        self.week_time_label.config(text=week_time)
        self.weekend_time_label.config(text=weekend_time)
        
        # 更新当天是否为周末的指示
        if self.monitor.is_weekend():
            self.is_weekend_label.config(text="(周末)")
        else:
            self.is_weekend_label.config(text="")
        
    def update_stats_display(self):
        """更新统计信息显示"""
        stats = self.monitor.get_stats()
        self._update_stats_labels(stats['today'], stats['week'], stats['weekend'])
        
        # 更新可用周列表
        if hasattr(self, 'week_combo') and self.week_combo:
            self.available_weeks = self.monitor.get_available_weeks()
            week_display_values = [f"{w['week_start_str']} 开始" for w in self.available_weeks] if self.available_weeks else ["无数据"]
            self.week_combo.config(values=week_display_values)
            current_week_start = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
            
            # 如果当前选择不在列表中，则选择匹配当前周的项或第一项
            if self.week_var.get() not in week_display_values:
                # 尝试找到当前周
                current_week_found = False
                for i, week in enumerate(self.available_weeks):
                    if week['date'] == current_week_start:
                        self.week_var.set(week_display_values[i])
                        current_week_found = True
                        break
                
                # 如果没找到当前周，选择第一项
                if not current_week_found and week_display_values and week_display_values[0] != "无数据":
                    self.week_var.set(week_display_values[0])
                    
        # 每秒更新一次
        self.root.after(1000, self.update_stats_display)
        
    def start_monitoring(self):
        """开始检测 - 使用固定30分钟间隔"""
        try:
            # 使用固定的30分钟间隔 (1800秒)
            self.monitor.interval = 1800
            
            # 启动检测
            self.monitor.start()
            
            # 更新按钮状态
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("错误", f"启动检测时出错: {e}")
            
    def toggle_pause(self):
        """切换暂停/恢复状态"""
        if self.monitor.paused:
            self.monitor.resume()
            self.pause_btn.config(text="暂停")
        else:
            self.monitor.pause()
            self.pause_btn.config(text="恢复")
            
    def stop_monitoring(self):
        """停止检测"""
        self.monitor.stop()
        
        # 更新按钮状态
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED, text="暂停")
        self.stop_btn.config(state=tk.DISABLED)
        
    def on_closing(self):
        """窗口关闭时的处理"""
        if self.monitor.running:
            if messagebox.askokcancel("退出", "检测正在进行中，确定退出吗？"):
                self.monitor.stop()
                self.monitor.cleanup()
                self.root.destroy()
        else:
            self.monitor.cleanup()
            self.root.destroy()


class AdminPanel:
    """管理员面板，用于查看所有用户的数据"""
    
    def __init__(self, root, auth_client):
        """初始化管理员面板
        
        Args:
            root: Tkinter根窗口
            auth_client: 已认证的客户端对象
        """
        self.root = root
        self.auth_client = auth_client
        
        # 检查管理员权限
        if not self.auth_client.is_admin():
            messagebox.showerror("错误", "需要管理员权限")
            self.root.destroy()
            return
        
        self._create_widgets()
        self._center_window()
        
        # 加载用户列表
        self.load_users()
        
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
        style.configure('Header.TLabel', font=('微软雅黑', 16, 'bold'))
        style.configure('User.TFrame', relief='solid')
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title_label = ttk.Label(main_frame, text="管理员面板", style='Header.TLabel')
        title_label.pack(pady=10)
        
        # 创建选项卡
        tab_control = ttk.Notebook(main_frame)
        tab_control.pack(fill=tk.BOTH, expand=1)
        
        # 用户列表选项卡
        users_tab = ttk.Frame(tab_control)
        tab_control.add(users_tab, text="用户列表")
        
        # 工作记录选项卡
        records_tab = ttk.Frame(tab_control)
        tab_control.add(records_tab, text="工作记录")
        
        # 用户列表框架
        users_frame = ttk.Frame(users_tab, padding=10)
        users_frame.pack(fill=tk.BOTH, expand=True)
        
        # 刷新按钮
        refresh_btn = ttk.Button(users_frame, text="刷新", command=self.load_users)
        refresh_btn.pack(pady=10)
        
        # 用户列表
        user_list_frame = ttk.LabelFrame(users_frame, text="用户列表", padding=10)
        user_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建用户列表的滚动区域
        user_scroll = ttk.Scrollbar(user_list_frame)
        user_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.user_list_canvas = tk.Canvas(user_list_frame, yscrollcommand=user_scroll.set)
        self.user_list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        user_scroll.config(command=self.user_list_canvas.yview)
        
        self.user_list_inner = ttk.Frame(self.user_list_canvas)
        self.user_list_canvas.create_window((0, 0), window=self.user_list_inner, anchor=tk.NW)
        
        self.user_list_inner.bind("<Configure>", lambda e: self.user_list_canvas.configure(
            scrollregion=self.user_list_canvas.bbox("all")
        ))
        
        # 工作记录框架
        records_frame = ttk.Frame(records_tab, padding=10)
        records_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户选择框架
        user_select_frame = ttk.Frame(records_frame)
        user_select_frame.pack(fill=tk.X, pady=10)
        
        user_select_label = ttk.Label(user_select_frame, text="选择用户:", width=15)
        user_select_label.pack(side=tk.LEFT)
        
        self.selected_user_var = tk.StringVar(value="所有用户")
        self.user_select_combo = ttk.Combobox(user_select_frame, textvariable=self.selected_user_var, 
                                            state="readonly", width=20)
        self.user_select_combo.pack(side=tk.LEFT, padx=5)
        
        # 查看按钮
        view_records_btn = ttk.Button(user_select_frame, text="查看记录", command=self.load_records)
        view_records_btn.pack(side=tk.LEFT, padx=10)
        
        # 记录列表
        record_list_frame = ttk.LabelFrame(records_frame, text="工作记录", padding=10)
        record_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建记录列表的滚动区域
        record_scroll = ttk.Scrollbar(record_list_frame)
        record_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.record_list_canvas = tk.Canvas(record_list_frame, yscrollcommand=record_scroll.set)
        self.record_list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        record_scroll.config(command=self.record_list_canvas.yview)
        
        self.record_list_inner = ttk.Frame(self.record_list_canvas)
        self.record_list_canvas.create_window((0, 0), window=self.record_list_inner, anchor=tk.NW)
        
        self.record_list_inner.bind("<Configure>", lambda e: self.record_list_canvas.configure(
            scrollregion=self.record_list_canvas.bbox("all")
        ))
        
    def load_users(self):
        """加载用户列表"""
        # 清除现有用户列表
        for widget in self.user_list_inner.winfo_children():
            widget.destroy()
            
        # 禁用刷新按钮
        for widget in self.user_list_inner.master.master.winfo_children():
            if isinstance(widget, ttk.Button) and widget['text'] == "刷新":
                widget.config(state=tk.DISABLED)
                
        # 在新线程中加载用户列表
        threading.Thread(target=self._load_users_thread, daemon=True).start()
        
    def _load_users_thread(self):
        """在线程中加载用户列表"""
        success, message, users = self.auth_client.get_all_users()
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_user_list(success, message, users))
        
    def _update_user_list(self, success, message, users):
        """更新用户列表"""
        # 重新启用刷新按钮
        for widget in self.user_list_inner.master.master.winfo_children():
            if isinstance(widget, ttk.Button) and widget['text'] == "刷新":
                widget.config(state=tk.NORMAL)
                
        if not success:
            messagebox.showerror("错误", message)
            return
            
        if not users:
            ttk.Label(self.user_list_inner, text="暂无用户").pack(pady=10)
            return
            
        # 更新用户选择下拉列表
        user_display_values = ["所有用户"] + [user['username'] for user in users]
        self.user_select_combo.config(values=user_display_values)
            
        # 添加用户列表项
        for user in users:
            user_frame = ttk.Frame(self.user_list_inner, style='User.TFrame', padding=10)
            user_frame.pack(fill=tk.X, pady=5)
            
            # 用户名
            username_label = ttk.Label(user_frame, text=f"用户名: {user['username']}")
            username_label.pack(anchor=tk.W)
            
            # 管理员标志
            if user.get('is_admin', False):
                admin_label = ttk.Label(user_frame, text="[管理员]", foreground='purple')
                admin_label.pack(anchor=tk.W)
            else:
                normal_label = ttk.Label(user_frame, text="[普通用户]", foreground='blue')
                normal_label.pack(anchor=tk.W)
            
            # 创建时间
            created_at = user.get('created_at', '未知')
            created_label = ttk.Label(user_frame, text=f"创建时间: {created_at}")
            created_label.pack(anchor=tk.W)
            
            # 查看按钮
            view_btn = ttk.Button(user_frame, text="查看记录", 
                              command=lambda u=user['username']: self.view_user_records(u))
            view_btn.pack(anchor=tk.W, pady=5)
            
    def view_user_records(self, username):
        """查看特定用户的记录"""
        self.selected_user_var.set(username)
        self.load_records()
        
    def load_records(self):
        """加载工作记录"""
        # 清除现有记录列表
        for widget in self.record_list_inner.winfo_children():
            widget.destroy()
            
        selected_user = self.selected_user_var.get()
        
        # 在新线程中加载记录
        threading.Thread(target=self._load_records_thread, args=(selected_user,), daemon=True).start()
        
    def _load_records_thread(self, selected_user):
        """在线程中加载记录"""
        if selected_user == "所有用户":
            success, message, records = self.auth_client.get_all_records()
        else:
            # 获取所有记录后过滤
            success, message, all_records = self.auth_client.get_all_records()
            if success:
                records = [r for r in all_records if r.get('username') == selected_user]
            else:
                records = []
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_record_list(success, message, records, selected_user))
        
    def _update_record_list(self, success, message, records, selected_user):
        """更新记录列表"""
        if not success:
            messagebox.showerror("错误", message)
            return
            
        if not records:
            ttk.Label(self.record_list_inner, text=f"暂无 {selected_user} 的记录").pack(pady=10)
            return
            
        # 添加记录列表项
        for record in sorted(records, key=lambda x: x.get('timestamp', ''), reverse=True):
            record_frame = ttk.Frame(self.record_list_inner, style='User.TFrame', padding=10)
            record_frame.pack(fill=tk.X, pady=5)
            
            # 用户名（如果显示所有用户）
            if selected_user == "所有用户":
                username_label = ttk.Label(record_frame, text=f"用户: {record.get('username', '未知')}")
                username_label.pack(anchor=tk.W)
            
            # 时间戳
            timestamp = record.get('timestamp', '未知时间')
            time_label = ttk.Label(record_frame, text=f"时间: {timestamp}")
            time_label.pack(anchor=tk.W)
            
            # 记录类型
            record_type = record.get('type', '未知类型')
            type_label = ttk.Label(record_frame, text=f"类型: {record_type}")
            type_label.pack(anchor=tk.W)
            
            # 数据预览
            if record_type == 'stats':
                try:
                    stats_data = json.loads(record.get('data', '{}'))
                    stats_preview = f"日期: {stats_data.get('date_str', '未知')}, " \
                                   f"时长: {stats_data.get('today', '00:00:00')}"
                    data_label = ttk.Label(record_frame, text=f"数据: {stats_preview}")
                    data_label.pack(anchor=tk.W)
                except:
                    data_label = ttk.Label(record_frame, text="数据: [统计数据]")
                    data_label.pack(anchor=tk.W)
            else:
                data_label = ttk.Label(record_frame, text="数据: [详细数据]")
                data_label.pack(anchor=tk.W)


def main():
    root = tk.Tk()
    
    def on_auth_success(auth_client):
        """认证成功后的回调函数"""
        # 隐藏认证窗口
        root.withdraw()
        
        # 创建新窗口显示监控界面
        monitor_window = tk.Toplevel(root)
        monitor_app = MonitoringGUI(monitor_window, auth_client)
        
        # 当监控窗口关闭时退出程序
        monitor_window.protocol("WM_DELETE_WINDOW", root.destroy)
    
    # 创建认证界面
    auth_app = AuthGUI(root, on_auth_success)
    
    root.mainloop()

if __name__ == "__main__":
    main()
