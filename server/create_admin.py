import json
import os
import sys
from werkzeug.security import generate_password_hash
import uuid
import datetime

def create_admin_user(username, password):
    """创建管理员用户
    
    Args:
        username: 管理员用户名
        password: 管理员密码
    """
    # 获取数据库文件路径
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.json")
    
    # 如果数据库文件不存在，创建一个空的数据库
    if not os.path.exists(db_file):
        with open(db_file, 'w', encoding='utf-8') as f:
            json.dump({
                "users": [],
                "work_records": []
            }, f, ensure_ascii=False, indent=2)
    
    # 加载数据库
    with open(db_file, 'r', encoding='utf-8') as f:
        db = json.load(f)
    
    # 检查用户名是否已存在
    if any(user['username'] == username for user in db['users']):
        print(f"错误: 用户名 '{username}' 已存在")
        return False
    
    # 创建管理员用户
    user_uid = str(uuid.uuid4())
    admin_user = {
        'uid': user_uid,
        'username': username,
        'password_hash': generate_password_hash(password),
        'is_admin': True,  # 设置为管理员
        'created_at': datetime.datetime.now().isoformat()
    }
    
    # 添加用户到数据库
    db['users'].append(admin_user)
    
    # 保存数据库
    with open(db_file, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    print(f"成功创建管理员用户 '{username}'")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python create_admin.py <用户名> <密码>")
        print("例如: python create_admin.py admin password123")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    create_admin_user(username, password)