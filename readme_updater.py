import os
import json
import re
import datetime
import logging

class ReadmeUpdater:
    """更新README.md文件中的周统计数据"""
    
    def __init__(self, root_dir):
        """初始化README更新器
        
        Args:
            root_dir: 项目根目录
        """
        self.root_dir = root_dir
        self.readme_path = os.path.join(root_dir, "README.md")
        self.weekly_stats_dir = os.path.join(root_dir, "monitoring_data", "stats", "weekly")
        
        self.logger = logging.getLogger('ReadmeUpdater')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
    def _read_readme(self):
        """读取README.md文件内容"""
        if os.path.exists(self.readme_path):
            with open(self.readme_path, 'r', encoding='utf-8') as file:
                return file.read()
        return ""
        
    def _write_readme(self, content):
        """写入README.md文件内容"""
        with open(self.readme_path, 'w', encoding='utf-8') as file:
            file.write(content)
            
    def _load_weekly_stats(self):
        """加载所有周统计数据"""
        stats_list = []
        
        if os.path.exists(self.weekly_stats_dir):
            for filename in os.listdir(self.weekly_stats_dir):
                if filename.startswith("week_") and filename.endswith(".json"):
                    file_path = os.path.join(self.weekly_stats_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file:
                            stats = json.load(file)
                            # 添加文件名，以便排序
                            stats['filename'] = filename
                            stats_list.append(stats)
                    except Exception as e:
                        self.logger.error(f"读取文件 {filename} 时出错: {e}")
                        
        # 按日期排序（从新到旧）
        stats_list.sort(key=lambda x: x.get('date', ''), reverse=True)
        return stats_list
        
    def _generate_stats_table(self, stats_list):
        """生成统计数据表格的Markdown格式"""
        if not stats_list:
            return "暂无统计数据"
            
        table = "| 周起始日期 | 总使用时长 | 工作日使用 | 周末使用 | 日均使用 |\n"
        table += "|------------|------------|------------|----------|----------|\n"
        
        for stats in stats_list:
            week_start = stats.get('week_start_str', stats.get('date_str', '未知'))
            total_time = stats.get('week', '00:00:00')
            weekend_time = stats.get('weekend', '00:00:00')
            
            # 计算工作日时间
            week_seconds = float(stats.get('week_seconds', 0))
            weekend_seconds = float(stats.get('weekend_seconds', 0))
            workday_seconds = max(0, week_seconds - weekend_seconds)
            
            # 格式化为小时:分钟:秒
            hours = int(workday_seconds // 3600)
            minutes = int((workday_seconds % 3600) // 60)
            seconds = int(workday_seconds % 60)
            workday_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # 计算日均使用时间
            avg_daily_seconds = week_seconds / 7
            hours = int(avg_daily_seconds // 3600)
            minutes = int((avg_daily_seconds % 3600) // 60)
            seconds = int(avg_daily_seconds % 60)
            avg_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            table += f"| {week_start} | {total_time} | {workday_time} | {weekend_time} | {avg_time} |\n"
            
        return table
        
    def update_readme(self):
        """更新README.md中的周统计数据"""
        try:
            # 读取当前README内容
            content = self._read_readme()
            
            # 加载所有周统计数据
            stats_list = self._load_weekly_stats()
            
            # 生成新的统计数据表格
            stats_table = self._generate_stats_table(stats_list)
            
            # 检查README是否已经包含统计数据部分
            stats_section_pattern = r"(## 周统计数据\n)(.*?)(\n##|\Z)"
            stats_section_match = re.search(stats_section_pattern, content, re.DOTALL)
            
            if stats_section_match:
                # 如果已存在，则替换内容
                new_content = content[:stats_section_match.start(2)] + stats_table + content[stats_section_match.end(2):]
            else:
                # 如果不存在，则添加新部分
                # 首先检查是否存在其他章节
                if "## " in content:
                    # 在第一个章节标题前插入
                    first_section_pos = content.find("## ")
                    new_content = (content[:first_section_pos] + 
                                  "## 周统计数据\n\n" + 
                                  stats_table + 
                                  "\n\n" + 
                                  content[first_section_pos:])
                else:
                    # 如果没有章节，则追加到文件末尾
                    new_content = content + "\n\n## 周统计数据\n\n" + stats_table + "\n"
                    
            # 写入更新后的README
            self._write_readme(new_content)
            self.logger.info("已更新README.md中的周统计数据")
            return True
        except Exception as e:
            self.logger.error(f"更新README.md时出错: {e}")
            return False
