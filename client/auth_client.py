import requests
import json
import os
import logging
from typing import Dict, Any, Tuple, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class AuthClient:
    """用户认证和API通信客户端"""
    
    def __init__(self, server_url="http://localhost:5000"):
        """初始化认证客户端
        
        Args:
            server_url: 服务器URL地址
        """
        self.server_url = server_url
        self.token = None
        self.user_info = None
        
        # 创建配置文件目录
        self.config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        self.token_file = os.path.join(self.config_dir, "auth_token.json")
        
        # 尝试加载保存的令牌
        self.load_token()
        
    def load_token(self) -> bool:
        """加载保存的令牌
        
        Returns:
            bool: 如果成功加载令牌返回True，否则返回False
        """
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.token = data.get('token')
                    self.user_info = data.get('user_info')
                    return True
            except Exception as e:
                logging.error(f"加载令牌时出错: {e}")
        return False
        
    def save_token(self):
        """保存令牌到本地文件"""
        if self.token and self.user_info:
            try:
                with open(self.token_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'token': self.token,
                        'user_info': self.user_info
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logging.error(f"保存令牌时出错: {e}")
                
    def clear_token(self):
        """清除保存的令牌"""
        self.token = None
        self.user_info = None
        if os.path.exists(self.token_file):
            try:
                os.remove(self.token_file)
            except Exception as e:
                logging.error(f"清除令牌文件时出错: {e}")
    
    def register(self, username: str, password: str) -> Tuple[bool, str]:
        """注册新用户
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        url = f"{self.server_url}/api/register"
        try:
            response = requests.post(url, json={
                'username': username,
                'password': password
            })
            
            if response.status_code == 201:
                logging.info("用户注册成功")
                return True, "注册成功"
            else:
                data = response.json()
                logging.error(f"注册失败: {data.get('message', '未知错误')}")
                return False, data.get('message', '注册失败')
        except Exception as e:
            logging.error(f"注册时出错: {e}")
            return False, f"请求错误: {e}"
            
    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        url = f"{self.server_url}/api/login"
        try:
            response = requests.post(url, json={
                'username': username,
                'password': password
            })
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                self.user_info = {
                    'uid': data.get('uid'),
                    'username': data.get('username'),
                    'is_admin': data.get('is_admin', False)
                }
                
                # 保存令牌
                self.save_token()
                
                logging.info(f"用户登录成功: {username}")
                return True, "登录成功"
            else:
                data = response.json()
                logging.error(f"登录失败: {data.get('message', '未知错误')}")
                return False, data.get('message', '登录失败')
        except Exception as e:
            logging.error(f"登录时出错: {e}")
            return False, f"请求错误: {e}"
            
    def logout(self):
        """用户登出"""
        self.clear_token()
        logging.info("用户已登出")
        
    def is_authenticated(self) -> bool:
        """检查用户是否已认证
        
        Returns:
            bool: 如果用户已认证返回True，否则返回False
        """
        return self.token is not None
        
    def is_admin(self) -> bool:
        """检查当前用户是否是管理员
        
        Returns:
            bool: 如果用户是管理员返回True，否则返回False
        """
        if not self.user_info:
            return False
        return self.user_info.get('is_admin', False)
        
    def get_username(self) -> str:
        """获取当前用户名
        
        Returns:
            str: 当前用户名，如未登录则返回空字符串
        """
        if not self.user_info:
            return ""
        return self.user_info.get('username', "")
        
    def get_uid(self) -> str:
        """获取当前用户ID
        
        Returns:
            str: 当前用户ID，如未登录则返回空字符串
        """
        if not self.user_info:
            return ""
        return self.user_info.get('uid', "")
        
    def get_headers(self) -> Dict[str, str]:
        """获取包含认证令牌的请求头
        
        Returns:
            Dict[str, str]: 请求头
        """
        if not self.token:
            return {}
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
    def upload_record(self, record_data: Dict[str, Any]) -> Tuple[bool, str]:
        """上传工作记录数据
        
        Args:
            record_data: 工作记录数据
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        if not self.is_authenticated():
            return False, "未登录"
            
        url = f"{self.server_url}/api/upload/record"
        try:
            headers = self.get_headers()
            response = requests.post(url, json=record_data, headers=headers)
            
            if response.status_code == 200:
                return True, "上传成功"
            else:
                data = response.json() if response.content else {"message": "未知错误"}
                return False, data.get('message', '上传失败')
        except Exception as e:
            logging.error(f"上传记录时出错: {e}")
            return False, f"请求错误: {e}"
            
    def upload_file(self, file_path, file_type=None):
        """上传文件
        
        Args:
            file_path: 文件路径
            file_type: 文件类型 (可选)
            
        Returns:
            tuple: (是否成功, 消息, 返回数据)
        """
        if not self.is_authenticated():
            return False, "未认证", None
            
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}", None
            
        try:
            # 准备文件
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f)}
                
                # 发送请求
                response = self._api_request('POST', 'upload/file', files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    return True, "上传成功", result.get('file_path')
                else:
                    error_msg = "上传失败"
                    try:
                        error_msg = response.json().get('message', error_msg)
                    except:
                        pass
                    return False, error_msg, None
        except Exception as e:
            return False, f"上传文件时出错: {str(e)}", None

    def get_user_records(self) -> Tuple[bool, str, list]:
        """获取当前用户的工作记录
        
        Returns:
            Tuple[bool, str, list]: (是否成功, 消息, 记录列表)
        """
        if not self.is_authenticated():
            return False, "未登录", []
            
        url = f"{self.server_url}/api/records"
        try:
            headers = self.get_headers()
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                records = response.json()
                return True, "获取成功", records
            else:
                data = response.json() if response.content else {"message": "未知错误"}
                return False, data.get('message', '获取失败'), []
        except Exception as e:
            logging.error(f"获取记录时出错: {e}")
            return False, f"请求错误: {e}", []
            
    def get_all_records(self) -> Tuple[bool, str, list]:
        """管理员获取所有用户的工作记录
        
        Returns:
            Tuple[bool, str, list]: (是否成功, 消息, 记录列表)
        """
        if not self.is_authenticated():
            return False, "未登录", []
            
        if not self.is_admin():
            return False, "需要管理员权限", []
            
        url = f"{self.server_url}/api/admin/records"
        try:
            headers = self.get_headers()
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                records = response.json()
                return True, "获取成功", records
            else:
                data = response.json() if response.content else {"message": "未知错误"}
                return False, data.get('message', '获取失败'), []
        except Exception as e:
            logging.error(f"获取所有记录时出错: {e}")
            return False, f"请求错误: {e}", []
            
    def get_all_users(self) -> Tuple[bool, str, list]:
        """管理员获取所有用户列表
        
        Returns:
            Tuple[bool, str, list]: (是否成功, 消息, 用户列表)
        """
        if not self.is_authenticated():
            return False, "未登录", []
            
        if not self.is_admin():
            return False, "需要管理员权限", []
            
        url = f"{self.server_url}/api/admin/users"
        try:
            headers = self.get_headers()
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                users = response.json()
                return True, "获取成功", users
            else:
                data = response.json() if response.content else {"message": "未知错误"}
                return False, data.get('message', '获取失败'), []
        except Exception as e:
            logging.error(f"获取所有用户时出错: {e}")
            return False, f"请求错误: {e}", []
        
    def _api_request(self, method, endpoint, data=None, files=None):
        """发送 API 请求
        
        Args:
            method: HTTP 方法 ('GET', 'POST', etc.)
            endpoint: API 端点 (不包含基础 URL)
            data: 请求数据 (字典)
            files: 上传的文件
            
        Returns:
            Response 对象
        """
        url = f"{self.server_url}/api/{endpoint}"
        headers = {}
        
        # 添加认证令牌
        if self.token:
            headers['Authorization'] = f"Bearer {self.token}"
        
        # 发送请求
        if method.upper() == 'GET':
            return requests.get(url, headers=headers, params=data)
        elif method.upper() == 'POST':
            if files:
                return requests.post(url, headers=headers, data=data, files=files)
            else:
                headers['Content-Type'] = 'application/json'
                return requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")

    def upload_weekly_stats(self, stats_file):
        """上传周统计数据
        
        Args:
            stats_file: 统计数据文件路径
            
        Returns:
            tuple: (是否成功, 消息, 返回数据)
        """
        if not self.is_authenticated():
            return False, "未认证", None
            
        try:
            # 读取周统计文件
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
                
            # 提取需要的数据
            if 'year' not in stats_data or 'week' not in stats_data:
                return False, "统计文件缺少年份或周数信息", None
                
            # 确保使用正确的属性名 - weekday_seconds 和 weekend_seconds
            weekday_seconds = stats_data.get('weekday_seconds', 0)
            weekend_seconds = stats_data.get('weekend_seconds', 0)
            
            # 构建请求数据
            data = {
                'year': stats_data['year'],
                'week': stats_data['week'],
                'weekday_seconds': int(weekday_seconds),  # 确保是整数类型
                'weekend_seconds': int(weekend_seconds)   # 确保是整数类型
            }
            
            # 发送请求
            response = self._api_request('POST', 'upload/weekly_stats', data=data)
            
            if response.status_code == 200:
                result = response.json()
                return True, "上传成功", result
            else:
                error_msg = "上传失败"
                try:
                    error_msg = response.json().get('message', error_msg)
                except:
                    pass
                return False, error_msg, None
                
        except FileNotFoundError:
            return False, f"找不到统计文件: {stats_file}", None
        except json.JSONDecodeError:
            return False, f"统计文件格式错误: {stats_file}", None
        except Exception as e:
            return False, f"上传统计数据时出错: {str(e)}", None

    def check_file_exists(self, file_hash: str, file_type: str = None) -> Tuple[bool, bool, Optional[str]]:
        """检查文件是否已存在于服务器
        
        Args:
            file_hash: 文件哈希值
            file_type: 文件类型，可选
            
        Returns:
            Tuple[bool, bool, Optional[str]]: (请求是否成功, 文件是否存在, 服务器上的文件路径)
        """
        if not self.is_authenticated():
            return False, False, None
            
        url = f"{self.server_url}/api/check_file"
        try:
            headers = self.get_headers()
            data = {'file_hash': file_hash}
            if file_type:
                data['file_type'] = file_type
                
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return True, data.get('exists', False), data.get('file_path')
            else:
                return False, False, None
        except Exception as e:
            logging.error(f"检查文件是否存在时出错: {e}")
            return False, False, None
            
    def upload_file_with_hash(self, file_path: str, file_type: str, file_hash: str = None) -> Tuple[bool, str, Optional[str]]:
        """上传文件并包含哈希值，用于增量上传
        
        Args:
            file_path: 文件路径
            file_type: 文件类型
            file_hash: 文件哈希值，如果为None则自动计算
            
        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 消息, 服务器端文件路径)
        """
        if not self.is_authenticated():
            return False, "未登录", None
            
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}", None
        
        # 如果未提供哈希值，则计算哈希值
        if file_hash is None:
            try:
                from file_sync import FileSyncManager
                sync_manager = FileSyncManager()
                file_hash = sync_manager.compute_file_hash(file_path)
            except Exception as e:
                logging.error(f"计算文件哈希值时出错: {e}")
                # 如果计算失败，尝试直接上传
                return self.upload_file(file_path, file_type)
        
        # 先检查文件是否已存在
        success, exists, remote_path = self.check_file_exists(file_hash, file_type)
        if success and exists and remote_path:
            # 文件已存在，无需重新上传
            logging.info(f"文件已存在于服务器: {os.path.basename(file_path)}")
            return True, "文件已存在于服务器", remote_path
            
        # 文件不存在或检查失败，上传文件
        url = f"{self.server_url}/api/upload/file_with_hash"
        try:
            headers = {
                'Authorization': f'Bearer {self.token}'
                # 注意：不要在这里设置Content-Type，因为requests会自动设置
            }
            
            with open(file_path, 'rb') as f:
                filename = os.path.basename(file_path)
                files = {'file': (filename, f, 'application/octet-stream')}
                data = {
                    'file_type': file_type,
                    'file_hash': file_hash
                }
                response = requests.post(url, files=files, data=data, headers=headers)
            
                if response.status_code == 200:
                    data = response.json()
                    return True, "文件上传成功", data.get('file_path')
                else:
                    data = response.json() if response.content else {"message": "未知错误"}
                    return False, data.get('message', '文件上传失败'), None
                    
        except Exception as e:
            logging.error(f"上传文件时出错: {e}")
            return False, f"请求错误: {e}", None