from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session, flash
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
import json
import uuid
from functools import wraps

# 导入简化后的数据库模型
from models import db, User, File, WeeklyStats

# 导入CSV相关库
import csv
import io
import itertools

app = Flask(__name__)
CORS(app)  # 启用跨域请求支持

# 配置信息
app.config['SECRET_KEY'] = 'your_secret_key'  # 实际应用中应该使用环境变量
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SERVER_VERSION'] = '1.1.0'  # 简化版服务器
app.config['API_COUNT'] = 0  # API请求计数器

# 初始化数据库
db.init_app(app)

# 记录服务器启动时间
server_start_time = datetime.datetime.now()
app.config['SERVER_START_TIME'] = server_start_time.strftime('%Y-%m-%d %H:%M:%S')

# 确保上传文件夹存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 在应用上下文中创建所有数据库表
with app.app_context():
    db.create_all()

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
            current_user = User.query.filter_by(uid=data['uid']).first()
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
        if not current_user.is_admin:
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
        
        user = User.query.filter_by(uid=session['user_id']).first()
        
        if not user or not user.is_admin:
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

    # 检查用户名是否已存在
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'message': '用户名已存在'}), 409

    # 创建新用户
    new_user = User(username=username, password=password, is_admin=is_admin)
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': '用户注册成功', 'uid': new_user.uid}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'用户注册失败: {str(e)}'}), 500

# 用户登录
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': '缺少必要参数'}), 400

    username = data['username']
    password = data['password']
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({'message': '用户名或密码错误'}), 401
    
    # 更新最后登录时间
    user.last_login = datetime.datetime.now()
    db.session.commit()
    
    # 生成JWT令牌
    token = jwt.encode({
        'uid': user.uid,
        'username': user.username,
        'is_admin': user.is_admin,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'message': '登录成功',
        'token': token,
        'uid': user.uid,
        'username': user.username,
        'is_admin': user.is_admin
    })

# 上传周工作时长统计
@app.route('/api/upload/weekly_stats', methods=['POST'])
@token_required
def upload_weekly_stats(current_user):
    data = request.get_json()
    if not data or not all(k in data for k in ['year', 'week', 'weekday_seconds', 'weekend_seconds']):
        return jsonify({'message': '缺少必要参数'}), 400
    
    # 确保转换为整数类型
    try:
        year = int(data['year'])
        week = int(data['week'])
        weekday_seconds = int(data['weekday_seconds'])
        weekend_seconds = int(data['weekend_seconds'])
    except (ValueError, TypeError):
        return jsonify({'message': '年份、周数或时长必须是有效数字'}), 400
    
    # 验证数据
    if not (1 <= week <= 53) or year < 2000:
        return jsonify({'message': '无效的年份或周数'}), 400
    
    # 检查是否已存在记录
    existing_stats = WeeklyStats.query.filter_by(
        user_id=current_user.id,
        year=year,
        week=week
    ).first()
    
    if existing_stats:
        # 更新已有记录
        existing_stats.weekday_duration = weekday_seconds
        existing_stats.weekend_duration = weekend_seconds
        existing_stats.upload_time = datetime.datetime.now()
        
        try:
            db.session.commit()
            return jsonify({
                'message': '周工作时长统计更新成功',
                'id': existing_stats.id
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'更新失败: {str(e)}'}), 500
    else:
        # 创建新记录
        new_stats = WeeklyStats(
            user_id=current_user.id,
            year=year,
            week=week,
            weekday_duration=weekday_seconds,
            weekend_duration=weekend_seconds
        )
        
        try:
            db.session.add(new_stats)
            db.session.commit()
            return jsonify({
                'message': '周工作时长统计上传成功',
                'id': new_stats.id
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'上传失败: {str(e)}'}), 500

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
        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_user.uid)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        
        # 获取当前日期信息用于创建年份_周数目录
        today = datetime.datetime.now()
        year = today.year
        week = today.isocalendar()[1]  # ISO周号
        week_dir_name = f"{year}_{week:02d}"
        
        # 创建年份_周数目录
        week_dir = os.path.join(user_dir, week_dir_name)
        if not os.path.exists(week_dir):
            os.makedirs(week_dir)
            
        # 创建时间戳目录 (YYYYMMDD_HHMMSS)
        timestamp_dir_name = today.strftime('%Y%m%d_%H%M%S')
        timestamp_dir = os.path.join(week_dir, timestamp_dir_name)
        if not os.path.exists(timestamp_dir):
            os.makedirs(timestamp_dir)
        
        # 保存文件
        file_path = os.path.join(timestamp_dir, file.filename)
        file.save(file_path)
        
        # 获取文件类型
        file_type = 'other'
        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            if 'screenshot' in file.filename.lower():
                file_type = 'screenshot'
            elif 'camera' in file.filename.lower():
                file_type = 'camera'
        elif file.filename.lower() == 'info.json':  # 新的文件名称
            file_type = 'applications'
            
        # 将文件记录保存到数据库
        relative_path = os.path.relpath(file_path, app.config['UPLOAD_FOLDER'])
        db_file = File(
            user_id=current_user.id,
            filename=file.filename,
            file_type=file_type,
            file_path=relative_path,
            file_date=today.date(),
            file_time=today.time()
        )
        
        try:
            db.session.add(db_file)
            db.session.commit()
            
            return jsonify({
                'message': '文件上传成功',
                'file_path': relative_path.replace('\\', '/'),
                'id': db_file.id
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'文件记录创建失败: {str(e)}'}), 500

# 管理员获取所有用户列表
@app.route('/api/admin/users', methods=['GET'])
@token_required
@admin_required
def get_all_users(current_user):
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

# 提供文件下载
@app.route('/api/files/<path:filename>')
@token_required
def get_file(current_user, filename):
    # 验证当前用户是否有权访问该文件
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    uid_from_path = filename.split('/')[0]
    
    if current_user.uid != uid_from_path and not current_user.is_admin:
        return jsonify({'message': '没有权限访问此文件'}), 403
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 获取用户每周统计数据
@app.route('/api/stats/weekly', methods=['GET'])
@token_required
def get_user_weekly_stats(current_user):
    # 获取参数（可选）：年份、周数
    year = request.args.get('year', type=int)
    week = request.args.get('week', type=int)
    
    # 构建查询
    query = WeeklyStats.query.filter_by(user_id=current_user.id)
    
    # 如果指定了年份或周数，则过滤
    if year:
        query = query.filter_by(year=year)
    if week:
        query = query.filter_by(week=week)
    
    # 按年份和周数排序
    stats = query.order_by(WeeklyStats.year.desc(), WeeklyStats.week.desc()).all()
    
    return jsonify([stat.to_dict() for stat in stats])

# 管理员获取所有用户的周统计数据
@app.route('/api/admin/stats/weekly', methods=['GET'])
@token_required
@admin_required
def admin_get_weekly_stats(current_user):
    # 获取参数（可选）：用户ID、年份、周数
    user_id = request.args.get('user_id')
    year = request.args.get('year', type=int)
    week = request.args.get('week', type=int)
    
    # 构建查询
    query = WeeklyStats.query
    
    # 如果指定了用户ID，则过滤
    if user_id:
        user = User.query.filter_by(uid=user_id).first()
        if user:
            query = query.filter_by(user_id=user.id)
    
    # 如果指定了年份或周数，则过滤
    if year:
        query = query.filter_by(year=year)
    if week:
        query = query.filter_by(week=week)
    
    # 分页支持
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)  # 默认每页20条
    
    # 按年份和周数倒序排序，分页
    pagination = query.order_by(WeeklyStats.year.desc(), 
                              WeeklyStats.week.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    # 返回分页数据
    return jsonify({
        'stats': [stat.to_dict() for stat in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

# ====================== Web界面路由 ======================

# 首页
@app.route('/')
def index():
    user_count = User.query.count()
    stats_count = WeeklyStats.query.count()
    
    # 计算文件数量
    file_count = File.query.count()
    
    return render_template('index.html', 
                          user_count=user_count, 
                          stats_count=stats_count, 
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
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return render_template('login.html', error='用户名或密码错误')
    
    if not user.is_admin:
        return render_template('login.html', error='需要管理员权限')
    
    # 更新最后登录时间
    user.last_login = datetime.datetime.now()
    db.session.commit()
    
    # 设置会话
    session['user_id'] = user.uid
    session['username'] = user.username
    session['is_admin'] = user.is_admin
    
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
    # 用户数据
    users = User.query.all()
    
    # 周统计数据 - 获取最近5条
    stats = WeeklyStats.query.order_by(
        WeeklyStats.year.desc(), 
        WeeklyStats.week.desc()
    ).limit(5).all()
    
    # 文件列表 - 获取最近12张图片
    files = File.query.filter(
        File.file_type.in_(['screenshot', 'camera'])
    ).order_by(File.timestamp.desc()).limit(12).all()
    
    # 转换文件列表为前端可用格式
    file_list = []
    for file in files:
        user = db.session.get(User, file.user_id)
        
        # 确保文件路径不为空且规范化
        safe_file_path = file.file_path.replace('\\', '/') if file.file_path else ""
        
        file_item = {
            'id': file.id,
            'filename': file.filename,
            'file_path': safe_file_path,
            'file_type': file.file_type,
            'date': file.file_date.isoformat() if file.file_date else None,
            'time': file.file_time.strftime('%H:%M:%S') if file.file_time else '',
            'username': user.username if user else 'unknown',
            'user_id': user.id if user else None,
            'url': f'/uploads/{safe_file_path}' if safe_file_path else ""  # 保留url字段，因为模板中直接用于img标签
        }
        file_list.append(file_item)
    
    # 计算文件总数
    file_count = File.query.count()
    
    return render_template('dashboard.html',
                          username=session.get('username', '管理员'),
                          users=[user.to_dict() for user in users],
                          stats=[stat.to_dict() for stat in stats],
                          files=file_list,
                          user_count=len(users),
                          stats_count=WeeklyStats.query.count(),
                          file_count=file_count,
                          server_status="正常运行",
                          server_start_time=app.config['SERVER_START_TIME'],
                          server_version=app.config['SERVER_VERSION'],
                          api_count=app.config['API_COUNT'])

# 用户管理页面
@app.route('/dashboard/users')
@admin_required_web
def dashboard_users():
    # 获取搜索参数
    search = request.args.get('search', '')
    role = request.args.get('role', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示10个用户
    
    # 构建基本查询
    query = User.query
    
    # 应用搜索过滤
    if search:
        query = query.filter(User.username.like(f'%{search}%'))
    
    # 应用角色过滤
    if role == 'admin':
        query = query.filter_by(is_admin=True)
    elif role == 'user':
        query = query.filter_by(is_admin=False)
    
    # 执行分页查询
    pagination = query.order_by(User.username).paginate(
        page=page, per_page=per_page, error_out=False)
    
    # 为每个用户添加统计数据和文件计数
    users_with_counts = []
    for user in pagination.items:
        user_dict = user.to_dict()
        user_dict['stats_count'] = WeeklyStats.query.filter_by(user_id=user.id).count()
        user_dict['file_count'] = File.query.filter_by(user_id=user.id).count()
        users_with_counts.append(user_dict)
    
    return render_template('users.html', 
                          username=session.get('username', '管理员'),
                          users=users_with_counts,
                          search=search,
                          role=role,
                          page=page,
                          pages=pagination.pages,
                          total=pagination.total)

# 文件管理页面
@app.route('/dashboard/files')
@admin_required_web
def dashboard_files():
    # 获取文件类型参数，用于过滤文件
    file_type = request.args.get('file_type', 'all')  # 修改为file_type以匹配表单字段
    user_id = request.args.get('user_id')  # 可选的用户过滤
    filename = request.args.get('filename', '')  # 添加文件名搜索功能
    start_date = request.args.get('start_date')  # 添加开始日期筛选
    end_date = request.args.get('end_date')  # 添加结束日期筛选
    sort_by = request.args.get('sort_by', 'date_desc')  # 默认按日期降序排序
    
    # 构建基本查询
    query = File.query
    
    # 应用文件类型过滤
    if file_type != 'all':
        query = query.filter_by(file_type=file_type)
    
    # 应用用户ID过滤
    if user_id and user_id != 'all':
        user = User.query.filter_by(uid=user_id).first()
        if user:
            query = query.filter_by(user_id=user.id)
    
    # 应用文件名搜索
    if filename:
        query = query.filter(File.filename.contains(filename))
    
    # 应用日期范围筛选
    if start_date:
        try:
            start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(File.file_date >= start_date_obj)
        except ValueError:
            pass  # 忽略无效的日期格式
    
    if end_date:
        try:
            end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(File.file_date <= end_date_obj)
        except ValueError:
            pass  # 忽略无效的日期格式
    
    # 应用排序
    if sort_by == 'date_asc':
        query = query.order_by(File.file_date.asc(), File.file_time.asc())
    elif sort_by == 'date_desc':
        query = query.order_by(File.file_date.desc(), File.file_time.desc())
    elif sort_by == 'name_asc':
        query = query.order_by(File.filename.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(File.filename.desc())
    elif sort_by == 'type':
        query = query.order_by(File.file_type.asc())
    elif sort_by == 'user':
        # 按用户名排序需要联接用户表
        query = query.join(User, File.user_id == User.id).order_by(User.username.asc())
    else:
        # 默认按时间戳降序
        query = query.order_by(File.timestamp.desc())
    
    # 分页支持
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 24, type=int)  # 每页显示24个文件
    
    # 查询文件并添加分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # 获取所有用户列表，供筛选使用
    all_users = User.query.all()
    
    # 转换文件列表为前端可用格式
    file_list = []
    for file in pagination.items:
        user = db.session.get(User, file.user_id)
        
        # 确保文件路径不为空且规范化
        safe_file_path = file.file_path.replace('\\', '/') if file.file_path else ""
        
        file_item = {
            'id': file.id,
            'filename': file.filename,
            'file_path': safe_file_path,
            'file_type': file.file_type,
            'date': file.file_date,
            'time': file.file_time.strftime('%H:%M:%S') if file.file_time else '',
            'username': user.username if user else 'unknown',
            'user_id': user.id if user else None
        }
        file_list.append(file_item)
    
    # 计算不同类型文件的数量，用于显示在过滤器中
    type_counts = {
        'all': File.query.count(),
        'screenshot': File.query.filter_by(file_type='screenshot').count(),
        'camera': File.query.filter_by(file_type='camera').count(),
        'applications': File.query.filter_by(file_type='applications').count(),
        'other': File.query.filter_by(file_type='other').count()
    }
    
    return render_template('files.html',
                          username=session.get('username', '管理员'),
                          files=file_list,
                          pagination=pagination,
                          pages=pagination.pages,
                          page=page,
                          file_type=file_type,
                          type_counts=type_counts,
                          all_users=all_users,  # 传递全部用户列表，而不只是users
                          selected_user_id=user_id,
                          filename=filename,
                          start_date=start_date,
                          end_date=end_date,
                          sort_by=sort_by,
                          per_page=per_page)

# 统计数据页面
@app.route('/dashboard/statistics')
@admin_required_web
def dashboard_statistics():
    # 获取用户ID参数过滤
    user_id = request.args.get('user_id')  
    year = request.args.get('year', datetime.datetime.now().year, type=int)
    
    # 获取所有用户以供选择
    users = User.query.all()
    
    # 构建查询
    query = WeeklyStats.query
    
    # 如果指定了用户，则过滤
    selected_username = "全部用户"
    if user_id:
        user = User.query.filter_by(uid=user_id).first()
        if user:
            query = query.filter_by(user_id=user.id)
            selected_username = user.username
    
    # 过滤年份        
    query = query.filter_by(year=year)
    
    # 按周数排序
    stats = query.order_by(WeeklyStats.week.asc()).all()
    
    # 准备图表数据和表格数据
    weeks = []
    weekday_hours = []
    weekend_hours = []
    total_hours = []
    
    stats_for_table = []
    total_weekday_seconds = 0
    total_weekend_seconds = 0
    
    for stat in stats:
        # 图表数据
        weeks.append(f"第{stat.week}周")
        weekday_hour = stat.weekday_duration // 3600
        weekend_hour = stat.weekend_duration // 3600
        total_hour = (stat.weekday_duration + stat.weekend_duration) // 3600
        
        weekday_hours.append(weekday_hour)
        weekend_hours.append(weekend_hour)
        total_hours.append(total_hour)
        
        # 累计时长统计
        total_weekday_seconds += stat.weekday_duration
        total_weekend_seconds += stat.weekend_duration
        
        # 表格数据
        user = db.session.get(User, stat.user_id)
        username = user.username if user else "未知用户"
        
        stats_for_table.append({
            'user_id': stat.user_id,
            'username': username,
            'week': stat.week,
            'weekday_hours': stat.format_duration(stat.weekday_duration),
            'weekend_hours': stat.format_duration(stat.weekend_duration),
            'total_hours': stat.format_duration(stat.weekday_duration + stat.weekend_duration),
            'daily_avg': stat.format_duration((stat.weekday_duration + stat.weekend_duration) // 7)
        })
    
    # 汇总时长格式化
    total_seconds = total_weekday_seconds + total_weekend_seconds
    total_hours_display = WeeklyStats.format_duration(None, total_seconds)
    weekday_hours_display = WeeklyStats.format_duration(None, total_weekday_seconds)
    weekend_hours_display = WeeklyStats.format_duration(None, total_weekend_seconds)
    
    # 获取可用年份列表
    available_years = db.session.query(WeeklyStats.year.distinct()).order_by(WeeklyStats.year.desc()).all()
    years = [y[0] for y in available_years]
    
    return render_template('statistics.html',
                          username=session.get('username', '管理员'),
                          users=users,
                          selected_user_id=user_id,
                          selected_username=selected_username,
                          current_year=year,
                          available_years=years,
                          stats=stats_for_table,
                          chart_labels=weeks,
                          chart_weekday_hours=weekday_hours,
                          chart_weekend_hours=weekend_hours,
                          chart_total_hours=total_hours,
                          total_hours_display=total_hours_display,
                          weekday_hours_display=weekday_hours_display,
                          weekend_hours_display=weekend_hours_display)

# 新增API路由：获取周详情 
@app.route('/api/week-detail')
@admin_required_web
def get_week_detail():
    try:
        # 获取查询参数
        year = request.args.get('year', type=int)
        week = request.args.get('week', type=int)
        user_id = request.args.get('user_id')
        
        if not all([year, week, user_id]):
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            })
        
        # 查询周统计数据
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '找不到用户'
            })
            
        week_stat = WeeklyStats.query.filter_by(
            user_id=user_id,
            year=year,
            week=week
        ).first()
        
        if not week_stat:
            return jsonify({
                'success': False,
                'message': '没有找到对应周的数据'
            })
        
        # 计算这一周的日期范围
        first_day_of_year = datetime.date(year, 1, 1)
        days_to_add = (week - 1) * 7
        if first_day_of_year.weekday() != 0:  # 如果1月1日不是周一
            days_to_add -= first_day_of_year.weekday()
        
        week_start_date = first_day_of_year + datetime.timedelta(days=days_to_add)
        week_end_date = week_start_date + datetime.timedelta(days=6)
        
        # 准备每天的详细数据 (这里是模拟数据，实际应从数据库获取)
        days_detail = []
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        # 从统计文件或数据库获取每天的工作记录
        # 此处仅生成模拟数据，实际应用中应从数据库查询
        current_date = week_start_date
        for i in range(7):
            is_weekend = i >= 5  # 周六周日是周末
            
            # 每天的工作时长，这里使用模拟数据
            if is_weekend:
                # 周末的时长分布
                if week_stat.weekend_duration > 0:
                    # 如果有周末时长，则按比例分配
                    if i == 5:  # 周六占60%
                        day_seconds = int(week_stat.weekend_duration * 0.6)
                    else:  # 周日占40%
                        day_seconds = int(week_stat.weekend_duration * 0.4)
                else:
                    day_seconds = 0
            else:
                # 工作日的时长，平均分配
                day_seconds = int(week_stat.weekday_duration / 5) if week_stat.weekday_duration > 0 else 0
            
            # 生成开始和结束时间
            start_time = "09:00:00" if day_seconds > 0 else "-"
            end_time = "17:00:00" if day_seconds > 0 else "-"
            
            days_detail.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'weekday': weekday_names[i],
                'is_weekend': is_weekend,
                'duration': week_stat.format_duration(day_seconds),
                'start_time': start_time,
                'end_time': end_time
            })
            
            current_date += datetime.timedelta(days=1)
        
        # 返回详细数据
        detail_data = {
            'username': user.username,
            'week_start': week_start_date.strftime('%Y-%m-%d'),
            'week_end': week_end_date.strftime('%Y-%m-%d'),
            'weekday_hours': week_stat.format_duration(week_stat.weekday_duration),
            'weekend_hours': week_stat.format_duration(week_stat.weekend_duration),
            'total_hours': week_stat.format_duration(week_stat.weekday_duration + week_stat.weekend_duration),
            'days': days_detail
        }
        
        return jsonify({
            'success': True,
            'detail': detail_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'发生错误: {str(e)}'
        })

# 统计数据导出API
@app.route('/dashboard/export_stats')
@admin_required_web
def export_stats():
    # 获取请求参数
    year = request.args.get('year', type=int)
    start_week = request.args.get('start_week', 1, type=int)
    end_week = request.args.get('end_week', 52, type=int)
    export_type = request.args.get('export_type', 'all_users')
    user_id = request.args.get('user_id')
    
    # 参数验证
    if not year:
        flash('请选择年份', 'danger')
        return redirect(url_for('dashboard_statistics'))
    
    if start_week < 1 or start_week > 52 or end_week < 1 or end_week > 52 or start_week > end_week:
        flash('周数范围无效', 'danger')
        return redirect(url_for('dashboard_statistics'))
    
    # 构建查询条件
    query = WeeklyStats.query.filter(
        WeeklyStats.year == year,
        WeeklyStats.week >= start_week,
        WeeklyStats.week <= end_week
    )
    
    # 如果只导出选定用户的数据
    if export_type == 'selected_user' and user_id:
        user = User.query.filter_by(uid=user_id).first()
        if user:
            query = query.filter_by(user_id=user.id)
    
    # 执行查询
    stats_data = query.order_by(WeeklyStats.user_id, WeeklyStats.week).all()
    
    if not stats_data:
        flash('所选条件下没有数据可导出', 'warning')
        return redirect(url_for('dashboard_statistics'))
    
    # 创建内存文件用于CSV
    csv_data = io.StringIO()
    csv_writer = csv.writer(csv_data)
    
    # 写入CSV标题行
    csv_writer.writerow([
        'ID', '用户ID', '用户名', '年份', '周数', '工作日时长(秒)', 
        '工作日时长(时:分:秒)', '周末时长(秒)', '周末时长(时:分:秒)', 
        '总时长(秒)', '总时长(时:分:秒)', '更新时间'
    ])
    
    # 写入数据行
    for stat in stats_data:
        user = db.session.get(User, stat.user_id)
        username = user.username if user else "未知用户"
        
        total_seconds = stat.weekday_duration + stat.weekend_duration
        
        csv_writer.writerow([
            stat.id,
            stat.user_id,
            username,
            stat.year,
            stat.week,
            stat.weekday_duration,
            stat.format_duration(stat.weekday_duration),
            stat.weekend_duration,
            stat.format_duration(stat.weekend_duration),
            total_seconds,
            stat.format_duration(total_seconds),
            stat.upload_time.isoformat() if stat.upload_time else ''
        ])
    
    # 设置响应headers
    filename = f"work_stats_{year}_W{start_week}-W{end_week}.csv"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Content-Type': 'text/csv; charset=utf-8'
    }
    
    # 返回CSV文件
    return csv_data.getvalue(), 200, headers

# 提供上传文件访问 - 增强错误处理
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """允许访问上传的文件，使图片预览功能正常工作"""
    try:
        app.logger.debug(f"Attempting to serve file: {filename}")
        if not filename or filename.strip() == '':
            app.logger.error("Empty filename requested")
            return "错误: 未指定文件名", 400
        
        # 修正可能的路径问题
        filename = filename.lstrip('/')
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            app.logger.error(f"File not found: {filepath}")
            return f"文件不存在: {filename}", 404
            
        directory = os.path.dirname(filepath)
        file_only = os.path.basename(filepath)
        
        if not file_only:  # 处理只请求目录的情况
            app.logger.error(f"Directory requested without file: {directory}")
            return "错误: 未指定文件名", 400
        
        return send_from_directory(directory, file_only)
    except Exception as e:
        app.logger.error(f"File access error: {str(e)}, filename: {filename}")
        return f"文件访问错误: {str(e)}", 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)