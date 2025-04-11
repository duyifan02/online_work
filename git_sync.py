import os
import subprocess
import logging
import time
from datetime import datetime

class GitSync:
    """处理Git同步操作的类"""
    
    def __init__(self, repo_dir, remote_url="https://github.com/duyifan02/online_work.git"):
        """初始化Git同步器
        
        Args:
            repo_dir: 本地仓库目录
            remote_url: 远程仓库URL
        """
        self.repo_dir = repo_dir
        self.remote_url = remote_url
        self.logger = logging.getLogger('GitSync')
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
    def _run_command(self, command, cwd=None):
        """运行Shell命令并返回结果
        
        Args:
            command: 要运行的命令列表
            cwd: 命令工作目录，默认为仓库目录
            
        Returns:
            tuple: (返回码, 标准输出, 标准错误)
        """
        if cwd is None:
            cwd = self.repo_dir
            
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                text=True
            )
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
        except Exception as e:
            self.logger.error(f"执行命令时出错: {e}")
            return -1, "", str(e)
    
    def is_git_repo(self):
        """检查目录是否为Git仓库"""
        git_dir = os.path.join(self.repo_dir, ".git")
        return os.path.exists(git_dir) and os.path.isdir(git_dir)
    
    def init_repo(self):
        """初始化Git仓库"""
        if not self.is_git_repo():
            self.logger.info("初始化Git仓库")
            returncode, stdout, stderr = self._run_command(["git", "init"])
            if returncode != 0:
                self.logger.error(f"初始化仓库失败: {stderr}")
                return False
                
            # 添加远程仓库
            returncode, stdout, stderr = self._run_command(
                ["git", "remote", "add", "origin", self.remote_url]
            )
            if returncode != 0:
                self.logger.error(f"添加远程仓库失败: {stderr}")
                return False
                
            return True
        return True
    
    def pull_changes(self):
        """从远程拉取更改"""
        self.logger.info("从远程拉取更改")
        
        # 先获取远程分支信息
        returncode, stdout, stderr = self._run_command(["git", "fetch"])
        if returncode != 0:
            self.logger.error(f"获取远程分支信息失败: {stderr}")
            return False
            
        # 检查是否有main分支
        returncode, stdout, stderr = self._run_command(["git", "branch"])
        has_main = "main" in stdout
        
        if not has_main:
            # 尝试创建main分支并与远程关联
            returncode, stdout, stderr = self._run_command(
                ["git", "checkout", "-b", "main", "origin/main"]
            )
            if returncode != 0:
                # 如果远程也没有main分支，则直接创建
                returncode, stdout, stderr = self._run_command(
                    ["git", "checkout", "-b", "main"]
                )
                if returncode != 0:
                    self.logger.error(f"创建main分支失败: {stderr}")
                    return False
        else:
            # 切换到main分支
            returncode, stdout, stderr = self._run_command(["git", "checkout", "main"])
            if returncode != 0:
                self.logger.error(f"切换到main分支失败: {stderr}")
                return False
        
        # 拉取更改，使用--allow-unrelated-histories解决初始同步问题
        returncode, stdout, stderr = self._run_command(
            ["git", "pull", "origin", "main", "--allow-unrelated-histories"]
        )
        # 对于首次拉取，忽略错误
        if stderr and "refusing to merge unrelated histories" in stderr:
            self.logger.warning("忽略不相关的历史记录错误，继续执行")
            return True
            
        if returncode != 0 and not ("CONFLICT" in stderr or "Already up to date" in stderr):
            self.logger.error(f"拉取更改失败: {stderr}")
            return False
            
        return True
    
    def commit_changes(self, message=None):
        """提交所有更改"""
        if message is None:
            message = f"自动同步 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
        # 添加所有文件
        self.logger.info("添加文件到暂存区")
        returncode, stdout, stderr = self._run_command(["git", "add", "."])
        if returncode != 0:
            self.logger.error(f"添加文件失败: {stderr}")
            return False
            
        # 提交更改
        self.logger.info("提交更改")
        returncode, stdout, stderr = self._run_command(
            ["git", "commit", "-m", message]
        )
        # 如果没有更改可提交，则认为是成功的
        if returncode != 0 and "nothing to commit" not in stderr:
            self.logger.error(f"提交更改失败: {stderr}")
            return False
            
        return True
    
    def push_changes(self):
        """推送更改到远程"""
        self.logger.info("推送更改到远程")
        returncode, stdout, stderr = self._run_command(
            ["git", "push", "-u", "origin", "main"]
        )
        if returncode != 0:
            if "Authentication failed" in stderr:
                self.logger.error("推送失败: 身份验证失败，请检查凭据")
            else:
                self.logger.error(f"推送更改失败: {stderr}")
            return False
            
        return True
    
    def sync(self, message=None):
        """执行完整的同步操作
        
        Returns:
            tuple: (成功状态, 消息)
        """
        try:
            # 初始化仓库（如果需要）
            if not self.init_repo():
                return False, "初始化Git仓库失败"
                
            # 拉取更改
            if not self.pull_changes():
                return False, "拉取远程更改失败"
                
            # 提交本地更改
            if not self.commit_changes(message):
                return False, "提交本地更改失败"
                
            # 推送更改到远程
            if not self.push_changes():
                return False, "推送更改到远程失败"
                
            return True, "同步成功完成"
        except Exception as e:
            self.logger.error(f"同步过程中出现异常: {e}")
            return False, f"同步失败: {str(e)}"
