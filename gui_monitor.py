import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
from monitor import MonitorSystem
import os
import webbrowser

class MonitoringGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("线上工作打卡控制面板")
        self.root.geometry("600x700")  # 增加高度以容纳周末时间显示
        self.root.resizable(False, False)
        
        # 初始化检测系统（固定10分钟间隔）
        self.monitor = MonitorSystem(interval=600)  # 固定为10分钟(600秒)
        self.monitor.set_status_callback(self.update_status)
        self.monitor.set_stats_callback(self.update_stats)
        
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
        stats_frame = ttk.LabelFrame(main_frame, text="使用统计", padding="10")
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
        
        fixed_interval_label = ttk.Label(interval_frame, text="10分钟", style='Info.TLabel')
        fixed_interval_label.pack(side=tk.LEFT, padx=5)
        
        # 创建按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        # 开始按钮
        self.start_btn = ttk.Button(btn_frame, text="开始", command=self.start_monitoring)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        # 暂停/恢复按钮
        self.pause_btn = ttk.Button(btn_frame, text="暂停", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=10)
        
        # 停止按钮
        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # 添加历史数据查看框架
        history_frame = ttk.LabelFrame(main_frame, text="历史数据", padding="10")
        history_frame.pack(fill=tk.X, pady=10)
        
        # 日期选择
        date_frame = ttk.Frame(history_frame)
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
        view_btn = ttk.Button(date_frame, text="查看数据", command=self.view_history_data)
        view_btn.pack(side=tk.LEFT, padx=10)
        
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
                
        # 每秒更新一次
        self.root.after(1000, self.update_stats_display)
        
    def start_monitoring(self):
        """开始检测 - 使用固定10分钟间隔"""
        try:
            # 使用固定的10分钟间隔 (600秒)
            self.monitor.interval = 600
            
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
