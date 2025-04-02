import cv2
import psutil
import time
import os
import datetime
import json
from PIL import ImageGrab
import numpy as np
import logging
import threading
import shutil

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class MonitorSystem:
    def __init__(self, interval=600):
        """初始化检测系统
        
        Args:
            interval: 检测间隔时间（秒）
        """
        # 设置保存目录
        self.SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitoring_data")
        if not os.path.exists(self.SAVE_DIR):
            os.makedirs(self.SAVE_DIR)
            
        # 设置统计数据文件
        self.STATS_DIR = os.path.join(self.SAVE_DIR, "stats")
        if not os.path.exists(self.STATS_DIR):
            os.makedirs(self.STATS_DIR)
        
        self.STATS_FILE = os.path.join(self.STATS_DIR, "usage_stats.json")
        
        # 设置当天日期目录
        self.current_date = datetime.datetime.now().strftime("%Y%m%d")
        self.update_daily_directory()
        
        self.interval = interval
        self.running = False
        self.paused = False
        self.thread = None
        self.status_callback = None
        
        # 计时相关变量
        self.start_time = None
        self.pause_time = None
        self.total_time_today = 0
        self.total_time_week = 0
        self.total_time_weekend = 0  # 新增：周末时间统计
        self.current_session_time = 0
        
        # 加载历史统计数据
        self.load_stats()
        
        # 启动统计更新线程
        self.stats_thread = threading.Thread(target=self._stats_update_loop, daemon=True)
        self.stats_thread_running = True
        self.stats_thread.start()
        
        # 启动日期检查线程
        self.date_check_thread = threading.Thread(target=self._date_check_loop, daemon=True)
        self.date_check_thread_running = True
        self.date_check_thread.start()

    def update_daily_directory(self):
        """更新当天的数据目录"""
        self.current_date = datetime.datetime.now().strftime("%Y%m%d")
        self.DAILY_DIR = os.path.join(self.SAVE_DIR, self.current_date)
        if not os.path.exists(self.DAILY_DIR):
            os.makedirs(self.DAILY_DIR)
            logging.info(f"创建新的日期目录: {self.DAILY_DIR}")

    def _date_check_loop(self):
        """日期检查循环，确保数据保存到正确的日期文件夹"""
        while self.date_check_thread_running:
            current_date = datetime.datetime.now().strftime("%Y%m%d")
            if current_date != self.current_date:
                self.update_daily_directory()
            time.sleep(60)  # 每分钟检查一次日期变化
    
    def set_status_callback(self, callback):
        """设置状态回调函数"""
        self.status_callback = callback
        
    def set_stats_callback(self, callback):
        """设置统计数据回调函数"""
        self.stats_callback = callback

    def is_weekend(self, date=None):
        """判断给定日期是否为周末（周六或周日）
        
        Args:
            date: 日期对象，如不提供则使用当天日期
            
        Returns:
            bool: 如果是周末返回True，否则返回False
        """
        if date is None:
            date = datetime.date.today()
        return date.weekday() >= 5  # 5=周六, 6=周日

    def capture_camera(self):
        """捕获摄像头画面"""
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logging.error("无法打开摄像头")
                return None
            
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return frame
            else:
                logging.error("无法捕获摄像头画面")
                return None
        except Exception as e:
            logging.error(f"捕获摄像头时出错: {e}")
            return None

    def get_active_applications(self):
        """获取当前运行的应用程序列表"""
        try:
            apps = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'status']):
                if proc.info['status'] == 'running':
                    apps.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'username': proc.info['username']
                    })
            return apps
        except Exception as e:
            logging.error(f"获取应用程序列表时出错: {e}")
            return []

    def capture_screenshot(self):
        """捕获屏幕截图"""
        try:
            screenshot = ImageGrab.grab()
            return np.array(screenshot)
        except Exception as e:
            logging.error(f"截取屏幕截图时出错: {e}")
            return None

    def save_monitoring_data(self):
        """保存检测数据 - 修改为按日期组织"""
        # 确保使用最新的日期目录
        self.update_daily_directory()
        
        # 创建时间戳子文件夹
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        timestamp_dir = os.path.join(self.DAILY_DIR, timestamp)
        if not os.path.exists(timestamp_dir):
            os.makedirs(timestamp_dir)
        
        # 保存摄像头画面
        camera_frame = self.capture_camera()
        if camera_frame is not None:
            cv2.imwrite(os.path.join(timestamp_dir, "camera.jpg"), camera_frame)
            logging.info(f"已保存摄像头画面到 {timestamp_dir}")
        
        # 保存屏幕截图
        screenshot = self.capture_screenshot()
        if screenshot is not None:
            cv2.imwrite(os.path.join(timestamp_dir, "screenshot.jpg"), 
                       cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR))
            logging.info(f"已保存屏幕截图到 {timestamp_dir}")
        
        # 保存应用程序列表
        apps = self.get_active_applications()
        with open(os.path.join(timestamp_dir, "applications.txt"), "w", encoding="utf-8") as f:
            f.write(f"记录时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("当前运行的应用程序:\n")
            for app in apps:
                f.write(f"PID: {app['pid']}, 名称: {app['name']}, 用户: {app['username']}\n")
        logging.info(f"已保存应用程序列表到 {timestamp_dir}")
        
        # 创建日期摘要文件 (如果不存在)
        summary_file = os.path.join(self.DAILY_DIR, "daily_summary.txt")
        if not os.path.exists(summary_file):
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"=== {self.current_date} 检测记录摘要 ===\n\n")
                
        # 追加本次记录到摘要
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp}: 记录完成 - 应用数量: {len(apps)}\n")

    def _monitoring_loop(self):
        """检测循环"""
        while self.running:
            if not self.paused:
                if self.status_callback:
                    self.status_callback("正在记录...")
                self.save_monitoring_data()
                if self.status_callback:
                    self.status_callback("等待下一次记录")
            
            # 每秒检查一次状态，这样可以及时响应暂停/恢复/停止
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
                
    def _stats_update_loop(self):
        """统计数据更新循环"""
        while self.stats_thread_running:
            # 如果正在运行且没有暂停，更新当前会话时间
            if self.running and not self.paused and self.start_time:
                current_time = time.time()
                self.current_session_time = current_time - self.start_time
                
                # 如果有回调，更新统计显示
                if hasattr(self, 'stats_callback') and self.stats_callback:
                    # 更新回调函数，增加周末时间参数
                    current_total = self.total_time_today + self.current_session_time
                    current_week = self.total_time_week + self.current_session_time
                    
                    # 如果是周末，也更新周末时间
                    current_weekend = self.total_time_weekend
                    if self.is_weekend():
                        current_weekend += self.current_session_time
                        
                    self.stats_callback(
                        self.format_time(current_total),
                        self.format_time(current_week),
                        self.format_time(current_weekend)
                    )
            
            # 每小时保存一次统计数据
            if self.running and not self.paused:
                self.save_stats()
                
            # 每天午夜重置当天的统计数据和更新日期目录
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0 and now.second < 5:  # 在0点的前5秒内执行
                self._reset_daily_stats()
                self.update_daily_directory()
                
            # 每周一重置每周的统计数据和周末时间
            if now.weekday() == 0 and now.hour == 0 and now.minute == 0 and now.second < 5:
                self._reset_weekly_stats()
                
            # 休眠一秒
            time.sleep(1)
                
    def load_stats(self):
        """加载统计数据"""
        try:
            if os.path.exists(self.STATS_FILE):
                with open(self.STATS_FILE, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
                    
                # 检查是否是今天的数据
                today = datetime.date.today().isoformat()
                if stats.get('date') == today:
                    self.total_time_today = stats.get('today', 0)
                else:
                    self.total_time_today = 0
                    
                # 检查是否是本周的数据
                # 获取本周的起始日期 (周一)
                today = datetime.date.today()
                week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()
                
                if stats.get('week_start') == week_start:
                    self.total_time_week = stats.get('week', 0)
                    self.total_time_weekend = stats.get('weekend', 0)  # 加载周末时间
                else:
                    self.total_time_week = 0
                    self.total_time_weekend = 0
        except Exception as e:
            logging.error(f"加载统计数据时出错: {e}")
            self.total_time_today = 0
            self.total_time_week = 0
            self.total_time_weekend = 0
            
    def save_stats(self):
        """保存统计数据 - 使用更一致和人性化的时间格式"""
        try:
            # 更新当前会话时间
            if self.running and not self.paused and self.start_time:
                current_time = time.time()
                self.current_session_time = current_time - self.start_time
                
            # 准备要保存的统计数据
            current_session = self.current_session_time if self.running and not self.paused else 0
            
            # 如果当前是周末，则更新周末时间
            current_weekend_session = 0
            if self.is_weekend() and self.running and not self.paused:
                current_weekend_session = current_session
            
            # 获取当前日期和时间
            now = datetime.datetime.now()
            today_date = datetime.date.today()
            week_start_date = today_date - datetime.timedelta(days=today_date.weekday())
            
            # 计算时间统计数据
            today_seconds = self.total_time_today + current_session
            week_seconds = self.total_time_week + current_session
            weekend_seconds = self.total_time_weekend + current_weekend_session
            
            # 创建易读的日期和时间格式
            date_str = today_date.strftime("%Y年%m月%d日")
            date_ymd = today_date.strftime("%Y-%m-%d")
            weekday_str = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today_date.weekday()]
            week_start_str = week_start_date.strftime("%Y年%m月%d日")
            last_update_str = now.strftime("%Y-%m-%d %H:%M:%S")
            
            stats = {
                # 标准ISO格式（用于计算）
                'date': today_date.isoformat(),
                'week_start': week_start_date.isoformat(),
                'last_update': now.isoformat(),
                
                # 人性化格式（用于显示）
                'date_str': date_str,
                'date_ymd': date_ymd,
                'weekday': weekday_str,
                'week_start_str': week_start_str,
                'last_update_str': last_update_str,
                
                # 秒数（用于计算）
                'today_seconds': today_seconds,
                'week_seconds': week_seconds,
                'weekend_seconds': weekend_seconds,
                
                # 格式化时间（用于显示）
                'today': self.format_time(today_seconds),
                'week': self.format_time(week_seconds),
                'weekend': self.format_time(weekend_seconds),
                
                # 状态标记
                'is_weekend': self.is_weekend()
            }
            
            # 保存到总统计文件
            with open(self.STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
                
            # 同时保存一份到当天的日期目录，方便按日期查看
            daily_stats_file = os.path.join(self.DAILY_DIR, "daily_stats.json")
            with open(daily_stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logging.error(f"保存统计数据时出错: {e}")
            
    def _reset_daily_stats(self):
        """重置每日统计"""
        if self.running and not self.paused:
            # 先更新每周统计，加上昨天的使用时间
            self.total_time_week += self.total_time_today
            
            # 如果昨天是周末，也要更新周末时间
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            if self.is_weekend(yesterday):
                self.total_time_weekend += self.total_time_today
            
        # 重置每日统计
        self.total_time_today = 0
        self.save_stats()
        logging.info("已重置每日统计数据")
        
    def _reset_weekly_stats(self):
        """重置每周统计和周末统计"""
        self.total_time_week = 0
        self.total_time_weekend = 0  # 同时重置周末时间
        self.save_stats()
        logging.info("已重置每周和周末统计数据")
        
    def format_time(self, seconds):
        """将秒数格式化为时:分:秒的形式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def start(self):
        """开始检测"""
        if self.thread and self.thread.is_alive():
            return
        
        self.running = True
        self.paused = False
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._monitoring_loop)
        self.thread.daemon = True
        self.thread.start()
        logging.info("检测程序已启动")
        if self.status_callback:
            self.status_callback("检测已启动")

    def pause(self):
        """暂停检测"""
        if not self.paused and self.start_time:
            # 计算到目前为止的会话时间并添加到总时间
            self.pause_time = time.time()
            pause_duration = self.pause_time - self.start_time
            self.total_time_today += pause_duration
            self.total_time_week += pause_duration
            
            # 如果是周末，也更新周末时间
            if self.is_weekend():
                self.total_time_weekend += pause_duration
                
            self.current_session_time = 0
            self.start_time = None
        
        self.paused = True
        logging.info("检测程序已暂停")
        if self.status_callback:
            self.status_callback("检测已暂停")
            
        # 保存统计数据
        self.save_stats()

    def resume(self):
        """恢复检测"""
        self.paused = False
        self.start_time = time.time()
        logging.info("检测程序已恢复")
        if self.status_callback:
            self.status_callback("等待下一次记录")

    def stop(self):
        """停止检测"""
        if self.running and not self.paused and self.start_time:
            # 计算最终会话时间并添加到总时间
            stop_time = time.time()
            session_duration = stop_time - self.start_time
            self.total_time_today += session_duration
            self.total_time_week += session_duration
            
            # 如果是周末，也更新周末时间
            if self.is_weekend():
                self.total_time_weekend += session_duration
                
            self.current_session_time = 0
            self.start_time = None
            
        self.running = False
        if self.thread:
            self.thread.join(1.0)  # 等待线程结束
        
        # 保存统计数据
        self.save_stats()
        
        logging.info("检测程序已停止")
        if self.status_callback:
            self.status_callback("检测已停止")
            
    def get_stats(self):
        """获取当前统计数据"""
        today_time = self.total_time_today
        week_time = self.total_time_week
        weekend_time = self.total_time_weekend
        
        # 如果正在运行，加上当前会话时间
        if self.running and not self.paused and self.start_time:
            current_session = time.time() - self.start_time
            today_time += current_session
            week_time += current_session
            
            # 如果是周末，也更新周末时间显示
            if self.is_weekend():
                weekend_time += current_session
            
        return {
            'today': self.format_time(today_time),
            'week': self.format_time(week_time),
            'weekend': self.format_time(weekend_time),
            'is_weekend': self.is_weekend()
        }
    
    def get_available_dates(self):
        """获取可用的历史日期目录列表"""
        try:
            dates = []
            for item in os.listdir(self.SAVE_DIR):
                item_path = os.path.join(self.SAVE_DIR, item)
                # 检查是否为目录且名称为8位数字(日期格式YYYYMMDD)
                if os.path.isdir(item_path) and len(item) == 8 and item.isdigit():
                    dates.append(item)
            return sorted(dates, reverse=True)  # 最新日期在前
        except Exception as e:
            logging.error(f"获取历史日期目录时出错: {e}")
            return []
        
    def cleanup(self):
        """清理资源"""
        self.stats_thread_running = False
        self.date_check_thread_running = False
        if self.running:
            self.stop()
        if self.stats_thread and self.stats_thread.is_alive():
            self.stats_thread.join(1.0)
        if self.date_check_thread and self.date_check_thread.is_alive():
            self.date_check_thread.join(1.0)

# 原有的main函数保留，以便可以直接运行此脚本
def main():
    """主函数"""
    monitor = MonitorSystem()
    try:
        monitor.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        monitor.cleanup()
        logging.info("程序已被用户中断")
    except Exception as e:
        logging.error(f"程序出现错误: {e}")

if __name__ == "__main__":
    main()
