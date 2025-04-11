import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
from monitor import MonitorSystem
from git_sync import GitSync
from readme_updater import ReadmeUpdater
import os
import webbrowser
import datetime

class MonitoringGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("线上工作打卡控制面板")
        self.root.geometry("600x800")  # 增加高度以容纳周末时间显示
        self.root.resizable(False, False)
        
        # 初始化检测系统（固定30分钟间隔）
        self.monitor = MonitorSystem(interval=1800)  # 固定为30分钟(1800秒)
        self.monitor.set_status_callback(self.update_status)
        self.monitor.set_stats_callback(self.update_stats)
        
        # 项目根目录
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 初始化Git同步器
        self.git_sync = GitSync(self.project_dir)
        
        # 初始化README更新器
        self.readme_updater = ReadmeUpdater(self.project_dir)
        
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
        style.configure('Sync.TButton', foreground='green')
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title_label = ttk.Label(main_frame, text="自动检测系统", font=('微软雅黑', 16, 'bold'))
        title_label.pack(pady=10)
        
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
        
        # 添加同步按钮框架
        sync_frame = ttk.Frame(main_frame)
        sync_frame.pack(fill=tk.X, pady=10)
        
        # 同步按钮
        self.sync_btn = ttk.Button(
            sync_frame, 
            text="同步数据", 
            command=self.sync_data,
            style='Sync.TButton'
        )
        self.sync_btn.pack(pady=5)
        
        # 同步状态标签
        self.sync_status_label = ttk.Label(sync_frame, text="未同步", style='Info.TLabel')
        self.sync_status_label.pack(pady=5)
        
        # 添加历史数据查看框架
        history_frame = ttk.LabelFrame(main_frame, text="历史数据", padding="10")
        history_frame.pack(fill=tk.X, pady=10)
        
        # 创建选项卡
        tab_control = ttk.Notebook(history_frame)
        tab_control.pack(fill=tk.BOTH, expand=1)
        
        # 日期选项卡
        date_tab = ttk.Frame(tab_control)
        tab_control.add(date_tab, text="按日期")
        
        # 日期选择
        date_frame = ttk.Frame(date_tab)
        date_frame.pack(fill=tk.X, pady=5)
        
        date_label = ttk.Label(date_frame, text="选择日期:", width=15)
        date_label.pack(side=tk.LEFT)
        
        # 获取可用日期列表
        available_dates = self.monitor.get_available_dates()
        
        self.date_var = tk.StringVar(value=available_dates[0] if available_dates else "无数据")
        self.date_combo = ttk.Combobox(date_frame, textvariable=self.date_var, 
                                      values=available_dates, 
                                      state="readonly", 
                                      width=15)
        self.date_combo.pack(side=tk.LEFT, padx=5)
        
        # 查看按钮
        view_date_btn = ttk.Button(date_frame, text="查看数据", command=self.view_history_data)
        view_date_btn.pack(side=tk.LEFT, padx=10)
        
        # 周选项卡
        week_tab = ttk.Frame(tab_control)
        tab_control.add(week_tab, text="按周")
        
        # 周选择框架
        week_select_frame = ttk.Frame(week_tab)
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
        self.week_stats_frame = ttk.Frame(week_tab)
        self.week_stats_frame.pack(fill=tk.BOTH, pady=10, expand=True)
        
        # 存储周数据备用
        self.available_weeks = available_weeks
        
        # 初始更新周统计显示
        if available_weeks:
            self.update_week_stats_display(available_weeks[0])
            
    def sync_data(self):
        """与GitHub同步数据"""
        # 禁用同步按钮，避免重复点击
        self.sync_btn.config(state=tk.DISABLED)
        self.sync_status_label.config(text="同步中...", foreground="blue")
        
        # 创建同步线程
        sync_thread = threading.Thread(target=self._sync_thread)
        sync_thread.daemon = True
        sync_thread.start()
        
    def _sync_thread(self):
        """在线程中执行同步，避免阻塞UI"""
        try:
            # 确保在同步前保存最新统计数据
            if hasattr(self, 'monitor') and self.monitor:
                self.monitor.save_stats()
                
            # 更新README.md中的统计数据
            self.root.after(0, lambda: self.sync_status_label.config(
                text="正在更新README...",
                foreground="blue"
            ))
            readme_updated = self.readme_updater.update_readme()
            if not readme_updated:
                self.root.after(0, lambda: self.sync_status_label.config(
                    text="README更新失败",
                    foreground="red"
                ))
                return
                
            # 执行Git同步
            self.root.after(0, lambda: self.sync_status_label.config(
                text="正在同步数据...",
                foreground="blue"
            ))
            success, message = self.git_sync.sync(
                f"自动同步统计数据 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # 更新UI
            if success:
                self.root.after(0, lambda: self.sync_status_label.config(
                    text=f"上次同步: {datetime.datetime.now().strftime('%d/%m/%Y,%H:%M:%S')}",
                    foreground="green"
                ))
            else:
                self.root.after(0, lambda: self.sync_status_label.config(
                    text=f"同步失败: {message}",
                    foreground="red"
                ))
        except Exception as e:
            self.root.after(0, lambda: self.sync_status_label.config(
                text=f"错误: {str(e)}",
                foreground="red"
            ))
        finally:
            # 重新启用同步按钮
            self.root.after(0, lambda: self.sync_btn.config(state=tk.NORMAL))
            
    def view_history_data(self):
        """查看历史数据"""
        selected_date = self.date_var.get()
        if (selected_date == "无数据"):
            messagebox.showinfo("提示", "没有可用的历史数据")
            return
            
        # 构建日期目录路径
        date_dir = os.path.join(self.monitor.SAVE_DIR, selected_date)
        
        if not os.path.exists(date_dir):
            messagebox.showerror("错误", f"无法找到 {selected_date} 的数据目录")
            return
            
        # 在文件资源管理器中打开该目录
        try:
            # Windows
            os.startfile(date_dir)
        except AttributeError:
            # Linux or macOS
            try:
                webbrowser.open(date_dir)
            except:
                messagebox.showinfo("提示", f"请手动浏览文件夹:\n{date_dir}")
        
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
        
        # 每隔一段时间更新可用日期列表
        if hasattr(self, 'date_combo') and self.date_combo:
            available_dates = self.monitor.get_available_dates()
            self.date_combo.config(values=available_dates)
            if not available_dates:
                self.date_var.set("无数据")
            elif self.date_var.get() not in available_dates:
                self.date_var.set(available_dates[0])
        
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

def main():
    root = tk.Tk()
    app = MonitoringGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
