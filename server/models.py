from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import datetime
import os

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    last_login = db.Column(db.DateTime)
    
    # 关系
    weekly_stats = db.relationship('WeeklyStats', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    files = db.relationship('File', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, username, password, is_admin=False):
        self.username = username
        self.set_password(password)
        self.is_admin = is_admin
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_password=False):
        data = {
            'id': self.id,
            'uid': self.uid,
            'username': self.username,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        if include_password:
            data['password_hash'] = self.password_hash
        return data

class File(db.Model):
    __tablename__ = 'files'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))  # 例如：screenshot, camera, applications
    file_path = db.Column(db.String(512), nullable=False)
    file_date = db.Column(db.Date, index=True)
    file_time = db.Column(db.Time)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'uid': self.user.uid,
            'username': self.user.username,
            'filename': self.filename,
            'file_type': self.file_type,
            'file_path': self.file_path,
            'file_date': self.file_date.isoformat() if self.file_date else None,
            'file_time': str(self.file_time) if self.file_time else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class WeeklyStats(db.Model):
    """简化的每周工作统计数据"""
    __tablename__ = 'weekly_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    year = db.Column(db.Integer, nullable=False)  # 年份
    week = db.Column(db.Integer, nullable=False)  # 周数 (1-52)
    weekday_duration = db.Column(db.Integer, default=0)  # 工作日工作时长（秒）
    weekend_duration = db.Column(db.Integer, default=0)  # 周末工作时长（秒）
    upload_time = db.Column(db.DateTime, default=datetime.datetime.now)
    
    # 添加唯一约束，确保每个用户每年每周只有一条记录
    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', 'week', name='unique_user_year_week'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'uid': self.user.uid,
            'username': self.user.username,
            'year': self.year,
            'week': self.week,
            'weekday_duration': self.weekday_duration,
            'weekday_hours': self.format_duration(self.weekday_duration),
            'weekend_duration': self.weekend_duration,
            'weekend_hours': self.format_duration(self.weekend_duration),
            'total_duration': self.weekday_duration + self.weekend_duration,
            'total_hours': self.format_duration(self.weekday_duration + self.weekend_duration),
            'upload_time': self.upload_time.isoformat() if self.upload_time else None
        }
    
    def format_duration(self, seconds):
        """将秒数格式化为时:分:秒格式"""
        if not seconds:
            return "00:00:00"
        
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"