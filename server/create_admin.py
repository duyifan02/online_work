import sys
import os
from flask import Flask
from models import db, User

def create_admin_user(username, password):
    """创建管理员用户
    
    Args:
        username: 管理员用户名
        password: 管理员密码
    """
    # 创建 Flask 应用
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 初始化数据库
    db.init_app(app)
    
    with app.app_context():
        # 确保数据库表存在
        db.create_all()
        
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"错误: 用户名 '{username}' 已存在")
            return False
        
        # 创建管理员用户
        admin_user = User(username=username, password=password, is_admin=True)
        
        # 添加用户到数据库
        try:
            db.session.add(admin_user)
            db.session.commit()
            print(f"成功创建管理员用户 '{username}'")
            print(f"用户 ID: {admin_user.uid}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"错误: 创建管理员用户失败 - {str(e)}")
            return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python create_admin.py <用户名> <密码>")
        print("例如: python create_admin.py admin password123")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    create_admin_user(username, password)