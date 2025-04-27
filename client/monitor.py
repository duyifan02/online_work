import cv2
import psutil
import time
import os
import datetime
import json
from PIL import Image, ImageGrab
import numpy as np
import logging
import threading
import shutil
import glob
import base64
import io
import hashlib
import cryptography
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import getpass
import socket

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def generate_encryption_key(salt=None):
    """生成基于固定密码的加密密钥"""
    # 使用固定密码
    password = "SYSU".encode()
    
    # 如果没有提供盐值，则使用固定盐值
    if salt is None:
        salt = b'fixed_salt_for_work_monitor'
    
    # 使用 PBKDF2HMAC 派生密钥
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

class MonitorSystem:
    def __init__(self, interval=600):
        """初始化检测系统
        
        Args:
            interval: 检测间隔时间（秒）
        """
        # 初始化加密密钥
        self.encryption_key = generate_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # 设置保存目录
        self.SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitoring_data")
        if not os.path.exists(self.SAVE_DIR):
            os.makedirs(self.SAVE_DIR)
            
        # 设置统计数据目录
        self.STATS_DIR = os.path.join(self.SAVE_DIR, "stats")
        if not os.path.exists(self.STATS_DIR):
            os.makedirs(self.STATS_DIR)
        
        # 设置记录数据目录
        self.RECORDS_DIR = os.path.join(self.SAVE_DIR, "records")
        if not os.path.exists(self.RECORDS_DIR):
            os.makedirs(self.RECORDS_DIR)
        
        # 获取当前日期信息
        today = datetime.date.today()
        self.current_year = today.year
        self.current_week = today.isocalendar()[1]  # ISO周号
        
        # 获取当前周的起始日期
        self.current_week_start = today - datetime.timedelta(days=today.weekday())
        
        # 构建当前周的目录和文件路径
        self.current_week_id = f"{self.current_year}_{self.current_week:02d}"
        self.current_week_dir = os.path.join(self.RECORDS_DIR, self.current_week_id)
        if not os.path.exists(self.current_week_dir):
            os.makedirs(self.current_week_dir)
            
        # 当前周统计文件 - 直接使用.enc扩展名
        self.current_week_file = os.path.join(self.STATS_DIR, f"{self.current_week_id}.enc")
        
        self.interval = interval
        self.running = False
        self.paused = False
        self.thread = None
        self.status_callback = None
        
        # 计时相关变量
        self.start_time = None
        self.pause_time = None
        self.weekday_time = 0    # 工作日时长
        self.weekend_time = 0    # 周末时长
        self.current_session_time = 0
        
        # 加载历史统计数据
        self.load_stats()
        
        # 启动统计更新线程
        self.stats_thread = threading.Thread(target=self._stats_update_loop, daemon=True)
        self.stats_thread_running = True
        self.stats_thread.start()
        
        # 单次计时会话跟踪变量
        self.current_session_start = None
        self.overtime_adjustment = 2 * 3600  # 超时调整: 2小时(秒)
        self.overtime_threshold = 12 * 3600  # 超时阈值: 12小时(秒)

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
        """保存检测数据 - 使用新的记录结构保存到周目录中，加密存储数据"""
        # 创建时间戳目录
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_dir = os.path.join(self.current_week_dir, timestamp)
        if not os.path.exists(timestamp_dir):
            os.makedirs(timestamp_dir)
        
        # 创建统一的记录数据结构
        record_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "formatted_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_weekend": self.is_weekend(),
            "session_duration": int(self.current_session_time) if self.current_session_time else 0,
            "apps": self.get_active_applications()
        }
        
        # 保存摄像头画面 (使用WebP格式)
        camera_frame = self.capture_camera()
        if camera_frame is not None:
            camera_image = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(camera_image)
            
            # 将图像保存到内存中
            img_bytes = io.BytesIO()
            pil_image.save(img_bytes, format="WebP", quality=85)
            img_bytes.seek(0)
            
            # 加密图像数据
            encrypted_data = self.cipher.encrypt(img_bytes.getvalue())
            
            # 保存加密后的图像数据
            camera_file = os.path.join(timestamp_dir, "camera.enc")
            with open(camera_file, "wb") as f:
                f.write(encrypted_data)
            logging.info(f"已加密保存摄像头图像到 {camera_file}")
        
        # 保存屏幕截图 (改为使用WebP格式而不是PNG，并缩小到50%尺寸)
        screenshot = self.capture_screenshot()
        if screenshot is not None:
            pil_screenshot = Image.fromarray(screenshot)
            
            # 获取原始尺寸
            original_width, original_height = pil_screenshot.size
            # 调整到50%尺寸
            new_width, new_height = original_width // 2, original_height // 2
            # 调整图像尺寸，使用LANCZOS重采样以保持较好的质量
            pil_screenshot = pil_screenshot.resize((new_width, new_height), Image.LANCZOS)
            
            # 将缩小后的截图保存到内存中，使用WebP格式
            img_bytes = io.BytesIO()
            pil_screenshot.save(img_bytes, format="WebP", quality=90)
            img_bytes.seek(0)
            
            # 加密截图数据
            encrypted_data = self.cipher.encrypt(img_bytes.getvalue())
            
            # 保存加密后的截图数据
            screenshot_file = os.path.join(timestamp_dir, "screenshot.enc")
            with open(screenshot_file, "wb") as f:
                f.write(encrypted_data)
            logging.info(f"已加密保存屏幕截图到 {screenshot_file} (已缩小到50%尺寸)")
        
        # 加密并保存记录数据
        record_file = os.path.join(timestamp_dir, "info.enc")
        json_data = json.dumps(record_data, ensure_ascii=False).encode('utf-8')
        encrypted_json = self.cipher.encrypt(json_data)
        
        with open(record_file, "wb") as f:
            f.write(encrypted_json)
        logging.info(f"已加密保存记录数据到 {record_file}")
        
        # 每次保存监控数据后也保存统计时长数据，防止意外中断导致数据丢失
        self.save_stats()
        logging.info("已更新统计时长数据")

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
                    current_weekday = self.weekday_time
                    current_weekend = self.weekend_time
                    
                    # 根据当前是否周末，更新对应的时间
                    if self.is_weekend():
                        current_weekend += self.current_session_time
                    else:
                        current_weekday += self.current_session_time
                        
                    # 计算总时间
                    current_total = current_weekday + current_weekend
                    
                    self.stats_callback(
                        self.format_time(current_weekday + current_weekend),  # 总时间
                        self.format_time(current_total),  # 周总时间
                        self.format_time(current_weekend)  # 周末时间
                    )
            
            # 移除每小时自动保存统计数据的功能
            # 只在程序暂停、停止或关闭时保存统计数据
                
            # 每周一重置周统计数据
            now = datetime.datetime.now()
            if now.weekday() == 0 and now.hour == 0 and now.minute == 0 and now.second < 5:
                self._reset_weekly_stats()
                
            # 休眠一秒
            time.sleep(1)
                
    def get_available_weeks(self):
        """获取所有可用的周统计数据"""
        weeks = []
        
        # 同时搜索 .json 和 .enc 格式的统计文件
        patterns = [
            os.path.join(self.STATS_DIR, "*.json"),
            os.path.join(self.STATS_DIR, "*.enc")
        ]
        
        processed_weeks = set()  # 用于跟踪已处理的周
        
        for pattern in patterns:
            for file_path in glob.glob(pattern):
                file_name = os.path.basename(file_path)
                
                # 提取文件名的基本部分 (YYYY_WW) 无论是 .json 还是 .enc
                base_name = file_name.split('.')[0]
                
                # 如果这个周已经处理过，跳过
                if base_name in processed_weeks:
                    continue
                processed_weeks.add(base_name)
                
                # 从文件名中提取年份和周号 (YYYY_WW)
                if "_" in base_name:
                    try:
                        year_week_parts = base_name.split('_')
                        if len(year_week_parts) != 2:
                            continue
                        
                        year = int(year_week_parts[0])
                        week = int(year_week_parts[1])
                        
                        # 计算该周的开始日期
                        first_day = datetime.date(year, 1, 1)
                        days_to_add = (week - 1) * 7
                        if first_day.weekday() != 0:  # 如果1月1日不是周一
                            days_to_add -= first_day.weekday()
                        
                        week_start_date = first_day + datetime.timedelta(days=days_to_add)
                        
                        # 尝试读取统计数据
                        stats = None
                        
                        # 首先尝试加密文件
                        enc_file = os.path.join(self.STATS_DIR, f"{base_name}.enc")
                        if os.path.exists(enc_file):
                            stats = self.decrypt_file(enc_file)
                        
                        # 如果加密文件不存在或无法解密，尝试明文文件
                        if stats is None:
                            json_file = os.path.join(self.STATS_DIR, f"{base_name}.json")
                            if os.path.exists(json_file):
                                with open(json_file, 'r', encoding='utf-8') as f:
                                    stats = json.load(f)
                        
                        # 如果获取到数据，构建周信息
                        if stats:
                            week_info = {
                                'date': week_start_date,
                                'week_start': stats.get('week_start', ''),
                                'week_start_str': stats.get('week_start_str', ''),
                                'weekday_seconds': float(stats.get('weekday_seconds', 0)),
                                'weekday': stats.get('weekday', '00:00:00'),
                                'weekend_seconds': float(stats.get('weekend_seconds', 0)),
                                'weekend': stats.get('weekend', '00:00:00'),
                                'week_seconds': float(stats.get('weekday_seconds', 0)) + float(stats.get('weekend_seconds', 0)),
                                'week': self.format_time(float(stats.get('weekday_seconds', 0)) + float(stats.get('weekend_seconds', 0))),
                                'file_path': file_path
                            }
                            weeks.append(week_info)
                        else:
                            # 如果无法读取任何文件，添加基本信息
                            weeks.append({
                                'date': week_start_date,
                                'week_start': week_start_date.isoformat(),
                                'week_start_str': week_start_date.strftime("%Y年%m月%d日"),
                                'weekday': '00:00:00',
                                'weekend': '00:00:00',
                                'weekday_seconds': 0,
                                'weekend_seconds': 0,
                                'week_seconds': 0,
                                'week': '00:00:00',
                                'file_path': file_path
                            })
                    except Exception as e:
                        logging.error(f"处理周统计文件出错: {e}, 文件: {file_path}")
                        continue
                    
        # 按日期降序排序（最近的周在前）
        weeks.sort(key=lambda x: x['date'], reverse=True)
        return weeks

    def load_stats(self):
        """加载统计数据"""
        try:
            # 首先尝试读取加密的统计文件
            stats_enc_file = self.current_week_file.replace('.json', '.enc')
            
            if os.path.exists(stats_enc_file):
                # 如果加密文件存在，解密并加载
                stats = self.decrypt_file(stats_enc_file)
                if stats:
                    # 检查是否是当前周的数据
                    today = datetime.date.today()
                    week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()
                    
                    if stats.get('week_start') == week_start:
                        # 加载工作日和周末时间
                        self.weekday_time = float(stats.get('weekday_seconds', 0))
                        self.weekend_time = float(stats.get('weekend_seconds', 0))
                        return
                    else:
                        # 新的一周，重置时间
                        self.weekday_time = 0
                        self.weekend_time = 0
                        return
            
            # 如果加密文件不存在或无法解密，尝试读取未加密的备份文件
            if os.path.exists(self.current_week_file):
                with open(self.current_week_file, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
                    
                # 检查是否是当前周的数据
                today = datetime.date.today()
                week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()
                
                if stats.get('week_start') == week_start:
                    # 加载工作日和周末时间
                    self.weekday_time = float(stats.get('weekday_seconds', 0))
                    self.weekend_time = float(stats.get('weekend_seconds', 0))
                else:
                    # 新的一周，重置时间
                    self.weekday_time = 0
                    self.weekend_time = 0
            else:
                # 没有找到任何统计数据文件
                self.weekday_time = 0
                self.weekend_time = 0
                
        except Exception as e:
            logging.error(f"加载统计数据时出错: {e}")
            self.weekday_time = 0
            self.weekend_time = 0
            
    def save_stats(self):
        """保存统计数据"""
        try:
            # 更新当前会话时间
            if self.running and not self.paused and self.start_time:
                current_time = time.time()
                self.current_session_time = current_time - self.start_time
                
            # 计算当前会话贡献的时间
            current_session = self.current_session_time if self.running and not self.paused else 0
            
            # 如果当前是周末，更新周末时间；否则更新工作日时间
            current_weekday_time = self.weekday_time
            current_weekend_time = self.weekend_time
            
            if self.is_weekend() and current_session > 0:
                current_weekend_time += current_session
            elif current_session > 0:
                current_weekday_time += current_session
            
            # 获取当前日期和时间
            today_date = datetime.date.today()
            week_start_date = today_date - datetime.timedelta(days=today_date.weekday())
            
            # 创建易读的日期格式
            week_start_str = week_start_date.strftime("%Y年%m月%d日")
            
            stats = {
                # 必要的信息
                'year': self.current_year,
                'week': self.current_week, 
                'week_start': week_start_date.isoformat(),
                'week_start_str': week_start_str,
                'weekday_seconds': current_weekday_time,
                'weekend_seconds': current_weekend_time,
                
                # 格式化时间（用于显示）
                'weekday': self.format_time(current_weekday_time),
                'weekend': self.format_time(current_weekend_time),
                'total': self.format_time(current_weekday_time + current_weekend_time),
                
                # 最后更新时间
                'last_update': datetime.datetime.now().isoformat()
            }
            
            # 只保存加密统计数据文件，不再保存明文JSON
            stats_enc_file = self.current_week_file.replace('.json', '.enc')
            json_data = json.dumps(stats, ensure_ascii=False).encode('utf-8')
            encrypted_json = self.cipher.encrypt(json_data)
            
            with open(stats_enc_file, 'wb') as f:
                f.write(encrypted_json)
                
            # 不再保存明文JSON文件
            # logging.info(f"已保存加密统计数据到 {stats_enc_file}")
                
        except Exception as e:
            logging.error(f"保存统计数据时出错: {e}")
            
    def decrypt_file(self, encrypted_file_path):
        """解密文件内容
        
        Args:
            encrypted_file_path: 加密文件路径
            
        Returns:
            解密后的数据，如果是JSON则返回解析后的对象，否则返回原始字节
        """
        try:
            with open(encrypted_file_path, 'rb') as f:
                encrypted_data = f.read()
                
            # 解密数据
            decrypted_data = self.cipher.decrypt(encrypted_data)
            
            # 尝试作为JSON解析
            if encrypted_file_path.endswith('.enc'):
                try:
                    return json.loads(decrypted_data.decode('utf-8'))
                except:
                    pass
                    
            return decrypted_data
        except Exception as e:
            logging.error(f"解密文件失败: {e}")
            return None
            
    def decrypt_image(self, encrypted_file_path, image_format="PNG"):
        """解密图像文件并返回PIL图像对象
        
        Args:
            encrypted_file_path: 加密的图像文件路径
            image_format: 图像格式，PNG或WebP
            
        Returns:
            PIL.Image对象，如果失败则返回None
        """
        try:
            decrypted_data = self.decrypt_file(encrypted_file_path)
            if decrypted_data:
                return Image.open(io.BytesIO(decrypted_data))
            return None
        except Exception as e:
            logging.error(f"解密图像失败: {e}")
            return None

    def _reset_weekly_stats(self):
        """重置每周统计"""
        # 在重置之前，确保当前周的数据已经保存
        self.save_stats()
        
        # 更新当前周的信息
        today = datetime.date.today()
        self.current_year = today.year
        self.current_week = today.isocalendar()[1]
        self.current_week_id = f"{self.current_year}_{self.current_week:02d}"
        
        # 更新周目录
        self.current_week_dir = os.path.join(self.RECORDS_DIR, self.current_week_id)
        if not os.path.exists(self.current_week_dir):
            os.makedirs(self.current_week_dir)
            logging.info(f"创建新的周目录: {self.current_week_dir}")
            
        # 更新周文件 - 使用.enc扩展名而非.json
        self.current_week_start = today - datetime.timedelta(days=today.weekday())
        self.current_week_file = os.path.join(self.STATS_DIR, f"{self.current_week_id}.enc")
        
        # 重置周统计数据
        self.weekday_time = 0
        self.weekend_time = 0
        self.save_stats()
        
        logging.info(f"已重置第{self.current_week}周统计数据")

    def format_time(self, seconds):
        """将秒数格式化为时:分:秒的形式"""
        try:
            # 确保seconds是数值类型
            seconds = float(seconds) if isinstance(seconds, str) else seconds
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        except (TypeError, ValueError) as e:
            logging.error(f"格式化时间出错: {e}, 提供的值: {seconds}, 类型: {type(seconds)}")
            return "00:00:00"  # 返回默认值

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

        # 记录会话开始时间
        self.current_session_start = time.time()

    def pause(self):
        """暂停检测"""
        if not self.paused and self.start_time:
            # 计算到目前为止的会话时间并添加到总时间
            self.pause_time = time.time()
            pause_duration = self.pause_time - self.start_time
            
            # 根据是否周末更新对应时间
            if self.is_weekend():
                self.weekend_time += pause_duration
            else:
                self.weekday_time += pause_duration
                
            self.current_session_time = 0
            self.start_time = None
        
        self.paused = True
        logging.info("检测程序已暂停")
        if self.status_callback:
            self.status_callback("检测已暂停")
            
        # 保存统计数据
        self.save_stats()

        # 处理可能的超时情况
        self._handle_session_end()

    def resume(self):
        """恢复检测"""
        self.paused = False
        self.start_time = time.time()
        logging.info("检测程序已恢复")
        if self.status_callback:
            self.status_callback("等待下一次记录")

        # 重新开始新会话计时
        self.current_session_start = time.time()

    def stop(self):
        """停止检测"""
        if self.running and not self.paused and self.start_time:
            # 计算最终会话时间并添加到总时间
            stop_time = time.time()
            session_duration = stop_time - self.start_time
            
            # 根据是否周末更新对应时间
            if self.is_weekend():
                self.weekend_time += session_duration
            else:
                self.weekday_time += session_duration
                
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

        # 处理可能的超时情况
        self._handle_session_end()

    def _handle_session_end(self):
        """处理会话结束，检查是否超时并相应调整累计时间"""
        if self.current_session_start is not None:
            session_duration = time.time() - self.current_session_start
            # 如果单次计时超过12小时，在累计时间中减去2小时
            if session_duration > self.overtime_threshold:
                self.status_callback(f"检测到单次计时超过12小时，自动减去2小时计时")
                # 更新总计时间，减去2小时调整
                adjustment_time = min(self.overtime_adjustment, session_duration - 1800)  # 至少保留30分钟
                # 更新相关统计数据
                self._adjust_stats_for_overtime(adjustment_time)
            
            # 重置会话开始时间
            self.current_session_start = None

    def _adjust_stats_for_overtime(self, adjustment_time):
        """调整因超时而需要减少的统计时间"""
        # 根据是否周末减少对应的时间
        if self.is_weekend():
            self.weekend_time -= adjustment_time
        else:
            self.weekday_time -= adjustment_time

    def get_stats(self):
        """获取当前统计数据"""
        weekday_time = self.weekday_time
        weekend_time = self.weekend_time
        
        # 如果正在运行，加上当前会话时间
        if self.running and not self.paused and self.start_time:
            current_session = time.time() - self.start_time
            
            # 根据是否周末添加到对应时间
            if self.is_weekend():
                weekend_time += current_session
            else:
                weekday_time += current_session
            
        # 计算总时间
        total_time = weekday_time + weekend_time
        
        return {
            'today': self.format_time(total_time),  # 保留today字段兼容性
            'week': self.format_time(total_time),
            'weekday': self.format_time(weekday_time),
            'weekend': self.format_time(weekend_time),
            'is_weekend': self.is_weekend()
        }
    
    def get_available_dates(self):
        """获取可用的记录日期列表"""
        try:
            dates = []
            # 遍历records目录下的所有周文件夹
            for week_dir in os.listdir(self.RECORDS_DIR):
                week_dir_path = os.path.join(self.RECORDS_DIR, week_dir)
                if os.path.isdir(week_dir_path):
                    # 遍历该周文件夹下的所有时间戳目录
                    for timestamp_dir in os.listdir(week_dir_path):
                        # 时间戳格式为 YYYYMMDD_HHMMSS
                        if '_' in timestamp_dir:
                            date_part = timestamp_dir.split('_')[0]
                            if len(date_part) == 8:  # YYYYMMDD
                                dates.append(date_part)
            
            # 去重和排序
            unique_dates = list(set(dates))
            return sorted(unique_dates, reverse=True)  # 最新日期在前
        except Exception as e:
            logging.error(f"获取可用日期列表时出错: {e}")
            return []

    def cleanup(self):
        """清理资源"""
        self.stats_thread_running = False
        if self.running:
            self.stop()
        if self.stats_thread and self.stats_thread.is_alive():
            self.stats_thread.join(1.0)

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
