from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
import json
import uuid
from functools import wraps

app = Flask(__name__)
CORS(app)  # 启用跨域请求支持

# 配置信息
app.config['SECRET_KEY'] = 'your_secret_key'  # 实际应用中应该使用环境变量
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['DATABASE_FILE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.json')
app.config['SERVER_VERSION'] = '1.0.0'  # 服务器版本
app.config['API_COUNT'] = 0  # API请求计数器

# 记录服务器启动时间
server_start_time = datetime.datetime.now()
app.config['SERVER_START_TIME'] = server_start_time.strftime('%Y-%m-%d %H:%M:%S')

# 确保上传文件夹存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 创建数据库初始结构（如果不存在）
if not os.path.exists(app.config['DATABASE_FILE']):
    with open(app.config['DATABASE_FILE'], 'w', encoding='utf-8') as f:
        json.dump({
            "users": [],
            "work_records": []
        }, f, ensure_ascii=False, indent=2)

# 加载数据库
def load_database():
    with open(app.config['DATABASE_FILE'], 'r', encoding='utf-8') as f:
        return json.load(f)

# 保存数据库
def save_database(data):
    with open(app.config['DATABASE_FILE'], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# API请求中间件：计数器和计时器
@app.before_request
def before_request():
    # 只计算API请求
    if request.path.startswith('/api'):
        app.config['API_COUNT'] += 1

# 用户认证装饰器 (API)
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'message': 'Token不存在'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            db = load_database()
            current_user = next((user for user in db['users'] if user['uid'] == data['uid']), None)
            if current_user is None:
                return jsonify({'message': '无效的用户'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token已过期'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': '无效的Token'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

# 管理员权限装饰器 (API)
def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if not current_user['is_admin']:
            return jsonify({'message': '需要管理员权限'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

# Web界面会话认证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Web界面管理员权限装饰器
def admin_required_web(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page', next=request.url))
        
        db = load_database()
        user = next((u for u in db['users'] if u['uid'] == session['user_id']), None)
        
        if not user or not user.get('is_admin', False):
            return render_template('login.html', error='需要管理员权限')
            
        return f(*args, **kwargs)
    return decorated_function

# ====================== API 路由 ======================
# 用户注册
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': '缺少必要参数'}), 400

    username = data['username']
    password = data['password']
    is_admin = data.get('is_admin', False)  # 默认为普通用户

    db = load_database()
    
    # 检查用户名是否已存在
    if any(user['username'] == username for user in db['users']):
        return jsonify({'message': '用户名已存在'}), 409

    # 创建新用户
    user_uid = str(uuid.uuid4())
    new_user = {
        'uid': user_uid,
        'username': username,
        'password_hash': generate_password_hash(password),
        'is_admin': is_admin,
        'created_at': datetime.datetime.now().isoformat()
    }
    
    db['users'].append(new_user)
    save_database(db)
    
    return jsonify({'message': '用户注册成功', 'uid': user_uid}), 201

# 用户登录
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': '缺少必要参数'}), 400

    username = data['username']
    password = data['password']
    
    db = load_database()
    user = next((u for u in db['users'] if u['username'] == username), None)
    
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'message': '用户名或密码错误'}), 401
    
    # 生成JWT令牌
    token = jwt.encode({
        'uid': user['uid'],
        'username': user['username'],
        'is_admin': user['is_admin'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'message': '登录成功',
        'token': token,
        'uid': user['uid'],
        'username': user['username'],
        'is_admin': user['is_admin']
    })

# 上传工作记录数据
@app.route('/api/upload/record', methods=['POST'])
@token_required
def upload_record(current_user):
    if not request.json:
        return jsonify({'message': '无效的数据格式'}), 400
    
    record_data = request.json
    record_data['uid'] = current_user['uid']
    record_data['username'] = current_user['username']
    record_data['timestamp'] = datetime.datetime.now().isoformat()
    
    db = load_database()
    db['work_records'].append(record_data)
    save_database(db)
    
    return jsonify({'message': '工作记录上传成功'})

# 上传文件（截图、摄像头等）
@app.route('/api/upload/file', methods=['POST'])
@token_required
def upload_file(current_user):
    if 'file' not in request.files:
        return jsonify({'message': '没有文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': '未选择文件'}), 400
    
    if file:
        # 创建用户目录
        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_user['uid'])
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        
        # 创建日期目录
        date_dir = os.path.join(user_dir, datetime.datetime.now().strftime('%Y%m%d'))
        if not os.path.exists(date_dir):
            os.makedirs(date_dir)
            
        # 创建时间戳目录
        timestamp_dir = os.path.join(date_dir, datetime.datetime.now().strftime('%H%M%S'))
        if not os.path.exists(timestamp_dir):
            os.makedirs(timestamp_dir)
        
        filename = os.path.join(timestamp_dir, file.filename)
        file.save(filename)
        
        return jsonify({
            'message': '文件上传成功',
            'file_path': filename.replace(os.path.dirname(os.path.abspath(__file__)), '').replace('\\', '/')
        })

# 获取当前用户的工作记录
@app.route('/api/records', methods=['GET'])
@token_required
def get_user_records(current_user):
    db = load_database()
    user_records = [record for record in db['work_records'] if record['uid'] == current_user['uid']]
    return jsonify(user_records)

# 管理员获取所有用户工作记录
@app.route('/api/admin/records', methods=['GET'])
@token_required
@admin_required
def get_all_records(current_user):
    db = load_database()
    return jsonify(db['work_records'])

# 管理员获取所有用户列表
@app.route('/api/admin/users', methods=['GET'])
@token_required
@admin_required
def get_all_users(current_user):
    db = load_database()
    # 不返回密码哈希
    users = [{k: v for k, v in user.items() if k != 'password_hash'} for user in db['users']]
    return jsonify(users)

# 提供文件下载
@app.route('/api/files/<path:filename>')
@token_required
def get_file(current_user, filename):
    # 验证当前用户是否有权访问该文件
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    uid_from_path = filename.split('/')[0]
    
    if current_user['uid'] != uid_from_path and not current_user['is_admin']:
        return jsonify({'message': '没有权限访问此文件'}), 403
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ====================== Web界面路由 ======================
# 首页
@app.route('/')
def index():
    db = load_database()
    user_count = len(db['users'])
    record_count = len(db['work_records'])
    
    # 计算文件数量
    file_count = 0
    uploads_dir = app.config['UPLOAD_FOLDER']
    if os.path.exists(uploads_dir):
        for root, dirs, files in os.walk(uploads_dir):
            file_count += len(files)
    
    return render_template('index.html', 
                          user_count=user_count, 
                          record_count=record_count, 
                          file_count=file_count,
                          server_status="正常运行",
                          server_start_time=app.config['SERVER_START_TIME'],
                          server_version=app.config['SERVER_VERSION'])

# 登录页面 (GET)
@app.route('/login', methods=['GET'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# 登录处理 (POST)
@app.route('/login', methods=['POST'])
def login_action():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return render_template('login.html', error='用户名和密码都不能为空')
    
    db = load_database()
    user = next((u for u in db['users'] if u['username'] == username), None)
    
    if not user or not check_password_hash(user['password_hash'], password):
        return render_template('login.html', error='用户名或密码错误')
    
    if not user.get('is_admin', False):
        return render_template('login.html', error='需要管理员权限')
    
    # 设置会话
    session['user_id'] = user['uid']
    session['username'] = user['username']
    session['is_admin'] = user['is_admin']
    
    next_url = request.args.get('next', url_for('dashboard'))
    return redirect(next_url)

# 登出
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 管理员仪表板
@app.route('/dashboard')
@admin_required_web
def dashboard():
    db = load_database()
    
    # 用户数据
    users = [{k: v for k, v in user.items() if k != 'password_hash'} for user in db['users']]
    
    # 工作记录
    records = sorted(db['work_records'], key=lambda r: r.get('timestamp', ''), reverse=True)
    records = records[:10]  # 只获取最近10条
    
    # 今日活跃用户数
    today = datetime.date.today().isoformat()
    active_today = len(set(r['uid'] for r in db['work_records'] if today in r.get('timestamp', '')))
    
    # 文件列表
    files = []
    uploads_dir = app.config['UPLOAD_FOLDER']
    if os.path.exists(uploads_dir):
        for root, dirs, filenames in os.walk(uploads_dir):
            for filename in filenames:
                if filename.endswith(('.jpg', '.jpeg', '.png')):
                    file_path = os.path.join(root, filename).replace('\\', '/')
                    relative_path = file_path.replace(uploads_dir, '').lstrip('/')
                    parts = relative_path.split('/')
                    if len(parts) >= 1:
                        user_id = parts[0]
                        user = next((u for u in db['users'] if u['uid'] == user_id), {'username': 'unknown'})
                        files.append({
                            'name': filename,
                            'url': f'/uploads/{relative_path}',
                            'type': 'image',
                            'user': user.get('username', 'unknown')
                        })
    files = files[:12]  # 只显示最近12个文件
    
    # 计算文件总数
    file_count = 0
    if os.path.exists(uploads_dir):
        for root, dirs, filenames in os.walk(uploads_dir):
            file_count += len(filenames)
    
    return render_template('dashboard.html',
                          username=session.get('username', '管理员'),
                          users=users,
                          records=records,
                          files=files,
                          user_count=len(users),
                          record_count=len(db['work_records']),
                          file_count=file_count,
                          active_today=active_today,
                          server_status="正常运行",
                          server_start_time=app.config['SERVER_START_TIME'],
                          server_version=app.config['SERVER_VERSION'],
                          api_count=app.config['API_COUNT'])

# 用户管理页面
@app.route('/dashboard/users')
@admin_required_web
def dashboard_users():
    # 重定向到仪表板，实际应用中应有单独的用户管理页面
    return redirect(url_for('dashboard'))

# 记录管理页面
@app.route('/dashboard/records')
@admin_required_web
def dashboard_records():
    # 重定向到仪表板，实际应用中应有单独的记录管理页面
    return redirect(url_for('dashboard'))

# 文件管理页面
@app.route('/dashboard/files')
@admin_required_web
def dashboard_files():
    # 重定向到仪表板，实际应用中应有单独的文件管理页面
    return redirect(url_for('dashboard'))

# 提供上传文件访问
@app.route('/uploads/<path:filename>')
@admin_required_web
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# API文档页面
@app.route('/api')
def api_docs():
    # 简单的API文档页面（可以扩展为更详细的文档）
    return render_template('index.html', 
                          server_status="正常运行",
                          server_start_time=app.config['SERVER_START_TIME'],
                          server_version=app.config['SERVER_VERSION'])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)