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

    def _time_string_to_hours(self, time_str):
        """将时间字符串 (HH:MM:SS) 转换为小时数"""
        try:
            h, m, s = map(int, time_str.split(':'))
            return h + m / 60 + s / 3600
        except (ValueError, AttributeError):
            return 0
    
    def _seconds_to_hours(self, seconds):
        """将秒数转换为小时数"""
        try:
            return float(seconds) / 3600
        except (ValueError, TypeError):
            return 0
    
    def _get_week_date_range(self, week_start_date_str):
        """计算周的日期区间（周一到周日）
        
        Args:
            week_start_date_str: 周开始日期字符串 (ISO格式 YYYY-MM-DD)
            
        Returns:
            str: 格式化的日期区间字符串
        """
        try:
            # 解析周开始日期（周一）
            if isinstance(week_start_date_str, str):
                year, month, day = map(int, week_start_date_str.split('-'))
                week_start = datetime.date(year, month, day)
            else:
                # 如果已经是date对象，直接使用
                week_start = week_start_date_str
                
            # 计算周结束日期（周日）
            week_end = week_start + datetime.timedelta(days=6)
            
            # 格式化为简洁的日期区间
            # 如果是同一个月，则显示为 "10.1-10.7, 2023"
            if week_start.month == week_end.month and week_start.year == week_end.year:
                return f"{week_start.month}.{week_start.day}-{week_end.day}, {week_start.year}"
            # 如果是同一年不同月，则显示为 "12.29-1.4, 2023"
            elif week_start.year == week_end.year:
                return f"{week_start.month}.{week_start.day}-{week_end.month}.{week_end.day}, {week_start.year}"
            # 如果是跨年，则显示为 "12.29, 2022 - 1.4, 2023"
            else:
                return f"{week_start.month}.{week_start.day}, {week_start.year} - {week_end.month}.{week_end.day}, {week_end.year}"
                
        except Exception as e:
            self.logger.error(f"计算周日期区间出错: {e}, 输入日期: {week_start_date_str}")
            return week_start_date_str  # 出错时返回原始值
        
    def _generate_stats_table(self, stats_list):
        """生成统计数据表格的Markdown格式"""
        if not stats_list:
            return "暂无统计数据"
            
        # 更新表格标题，将"周起始日期"改为"周日期区间"
        table = "| 周日期区间 | 总使用时长 | 工作日使用 | 周末使用 | 日均使用 | 状态 |\n"
        table += "|------------|------------|------------|----------|----------|------|\n"
        
        for stats in stats_list:
            # 获取周起始日期的ISO格式（YYYY-MM-DD）
            week_start_iso = stats.get('week_start', '')
            
            # 如果没有ISO格式，尝试使用原有的显示格式
            if not week_start_iso:
                week_date_range = stats.get('week_start_str', '未知')
            else:
                # 计算并格式化周的日期区间
                week_date_range = self._get_week_date_range(week_start_iso)
            
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
            
            # 判断是否满足状态条件：总时长>50小时且周末>5小时
            # 方法1：直接使用秒数计算
            total_hours = week_seconds / 3600
            weekend_hours = weekend_seconds / 3600
            
            # 方法2：如果没有秒数，则使用格式化的时间字符串
            if week_seconds == 0:
                total_hours = self._time_string_to_hours(total_time)
            if weekend_seconds == 0:
                weekend_hours = self._time_string_to_hours(weekend_time)
                
            # 确定状态标记
            status = "✅" if total_hours > 50 and weekend_hours > 5 else "❎"
            
            table += f"| {week_date_range} | {total_time} | {workday_time} | {weekend_time} | {avg_time} | {status} |\n"
            
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
