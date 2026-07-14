详细的部署指南，包括：
    1. 项目准备
    2. 宝塔面板部署
    3. 1Panel面板部署
    4. 其他通用方式

    让我为用户创建一个详细的部署指南文档。


    现在我了解了这个项目的结构。这是一个Flask应用，需要连接PostgreSQL数据库。让我为你创建一个详细的部署指南。

    项目分析

    | 项目   | 说明                                 |
    |--------|--------------------------------------|
    | 类型   | Flask Web应用（Token额度查询平台）   |
    | 依赖   | Flask==3.0.0, psycopg2-binary==2.9.9 |
    | 数据库 | PostgreSQL                           |
    | 端口   | 5000                                 |



    部署指南

    方式一：宝塔面板部署

    1. 上传项目文件
    在宝塔中创建网站，将项目文件上传到 /www/wwwroot/token-query/

    2. 安装Python项目环境
    bash
    进入网站目录
    cd /www/wwwroot/token-query/

    创建虚拟环境
    python3 -m venv venv

    激活虚拟环境
    source venv/bin/activate

    安装依赖
    pip install -r requirements.txt


    3. 修改配置文件
    编辑 config.py，修改数据库连接信息为你的实际配置：
    python
    DB_CONFIG = {
        'host': '你的数据库地址',
        'port': 5432,
        'database': 'new-api',
        'user': '数据库用户名',
        'password': '数据库密码'
    }

    可选：修改应用端口
    APP_PORT = 5000


    4. 使用PM2管理进程（推荐）
    bash
    安装PM2
    npm install -g pm2

    创建启动脚本 start.sh
    cat > start.sh << 'EOF'
    #!/bin/bash
    source venv/bin/activate
    cd /www/wwwroot/token-query
    export PYTHONUNBUFFERED=1
    exec gunicorn -w 2 -b 0.0.0.0:5000 app:app
    EOF
    chmod +x start.sh

    使用PM2启动
    pm2 start start.sh --name token-query
    pm2 save
    pm2 startup


    5. 或使用Supervisor管理
    在宝塔软件商店安装Supervisor，添加配置：
    ini
    [program:token-query]
    directory=/www/wwwroot/token-query
    command=/www/wwwroot/token-query/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
    user=www
    autostart=true
    autorestart=true
    stopasgroup=true
    killasgroup=true
    stderr_logfile=/www/wwwroot/token-query/logs/error.log
    stdout_logfile=/www/wwwroot/token-query/logs/out.log


    6. 配置反向代理（可选）
    如果需要通过域名访问，在宝塔网站设置中添加反向代理：
    - 目标URL：http://127.0.0.1:5000
    - 发送域名：$host



    方式二：1Panel面板部署

    1. 上传项目文件
    在1Panel中创建应用，将项目文件上传到 /opt/1panel/apps/token-query/ 或你选择的目录

    2. 创建Python应用
    在1Panel中：
    1. 容器/应用 → 创建应用 → 自定义
    2. 选择 Python 运行环境
    3. 配置：
       - 工作目录：选择项目路径
       - 启动命令：gunicorn -w 2 -b 0.0.0.0:5000 app:app

    3. 安装依赖
    bash
    cd /opt/1panel/apps/token-query
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt


    4. 修改配置
    编辑 config.py 中的数据库连接信息

    5. 使用1Panel应用商店（如有）
    如果1Panel商店有类似应用模板，可以参考其配置方式



    方式三：使用Docker部署（通用）

    创建Dockerfile
    dockerfile
    FROM python:3.12-slim

    WORKDIR /app

    安装系统依赖
    RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        && rm -rf /var/lib/apt/lists/*

    复制依赖文件
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt gunicorn

    复制应用代码
    COPY . .

    创建非root用户
    RUN useradd -m appuser && chown -R appuser:appuser /app
    USER appuser

    EXPOSE 5000

    CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]


    创建docker-compose.yml
    yaml
    version: '3.8'
    services:
      token-query:
        build: .
        ports:
          - "5000:5000"
        environment:
          - DB_HOST=192.168.10.21
          - DB_PORT=5432
          - DB_NAME=new-api
          - DB_USER=root
          - DB_PASSWORD=123456
        restart: unless-stopped


    注意：需要修改 app.py 和 config.py 使用环境变量获取数据库配置



    方式四：直接命令行运行（开发/测试）

    bash
    cd /root/.hermes/plugin/token-query

    激活虚拟环境
    source venv/bin/activate

    启动应用
    python app.py




    部署后验证

    bash
    检查进程是否运行
    curl http://localhost:5000/

    或检查API接口
    curl "http://localhost:5000/api/query?key=test_key"




    常见问题

    | 问题            | 解决方案                                               |
    |-----------------|--------------------------------------------------------|
    | 数据库连接失败  | 检查防火墙、数据库是否允许远程连接、用户名密码是否正确 |
    | 端口被占用      | 更换 APP_PORT 或杀死占用进程                           |
    | 静态文件404     | 确保 static/ 和 templates/ 在项目根目录                |
    | Unicode编码错误 | 数据库连接字符串添加 client_encoding=utf8              |



    需要我帮你修改配置文件以支持环境变量配置吗？这样更容易在不同环境中部署。
