"""
Token 额度查询平台 - Flask 主应用
只进行数据库读操作，不做任何写入
"""

from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from config import DB_CONFIG, EXCHANGE_RATE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

app = Flask(__name__)

# 东八区时区
TZ_EAST_8 = timezone(timedelta(hours=8))


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def timestamp_to_datetime(timestamp):
    """将Unix时间戳转换为东八区可读时间字符串"""
    if timestamp is None or timestamp == -1:
        return None
    try:
        ts = int(timestamp)
        if ts <= 0:
            return None
        dt = datetime.fromtimestamp(ts, tz=TZ_EAST_8)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OSError):
        return None


def timestamp_to_date_str(timestamp):
    """将Unix时间戳转换为日期字符串（用于统计）"""
    if timestamp is None or timestamp <= 0:
        return None
    try:
        dt = datetime.fromtimestamp(int(timestamp), tz=TZ_EAST_8)
        return dt.strftime('%Y/%m/%d')
    except (ValueError, OSError):
        return None


def timestamp_to_datetime_str(timestamp):
    """将Unix时间戳转换为日期时间字符串（用于日志列表）"""
    if timestamp is None or timestamp <= 0:
        return None
    try:
        dt = datetime.fromtimestamp(int(timestamp), tz=TZ_EAST_8)
        return dt.strftime('%Y/%m/%d %H:%M:%S')
    except (ValueError, OSError):
        return None


def get_time_range_range(time_range):
    """获取时间范围的开始和结束时间戳"""
    now = datetime.now(tz=TZ_EAST_8)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if time_range == 'today':
        start = today_start
        end = now
    elif time_range == 'yesterday':
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start
        start = yesterday_start
        end = yesterday_end
    elif time_range == 'last_3_days':
        start = today_start - timedelta(days=2)
        end = now
    elif time_range == 'last_7_days':
        start = today_start - timedelta(days=6)
        end = now
    elif time_range == 'last_30_days':
        start = today_start - timedelta(days=29)
        end = now
    else:
        # 默认近7天
        start = today_start - timedelta(days=6)
        end = now

    return int(start.timestamp()), int(end.timestamp())


def mask_key(key):
    """将Key脱敏显示"""
    if not key or len(key) < 10:
        return key
    return f"{key[:10]}...{key[-4:]}"


def quota_to_yuan(quota):
    """将配额转换为元（保留2位小数）"""
    if quota is None:
        return "0.00"
    try:
        # 将Decimal或其他数值类型转换为float
        quota_float = float(quota)
        yuan = abs(quota_float) / EXCHANGE_RATE
        return f"{yuan:.2f}"
    except (ValueError, ZeroDivisionError):
        return "0.00"


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


def normalize_key(key):
    """规范化Key：去掉sk-前缀（如果存在）"""
    if not key:
        return key
    # 去掉sk-前缀（如果有）
    if key.startswith('sk-'):
        return key[3:]
    return key


@app.route('/api/query', methods=['GET'])
def query_token():
    """
    查询Token额度信息
    参数：key - API Key
    """
    key = request.args.get('key', '').strip()

    if not key:
        return jsonify({
            'success': False,
            'error': '请输入 API Key'
        })

    # 规范化Key：去掉sk-前缀
    normalized_key = normalize_key(key)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 查询token信息（使用规范化的key，去掉sk-前缀）
        cur.execute("""
            SELECT id, key, name, status, created_time, accessed_time,
                   expired_time, remain_quota, used_quota, unlimited_quota
            FROM tokens
            WHERE key = %s AND deleted_at IS NULL
        """, (normalized_key,))

        token = cur.fetchone()
        cur.close()
        conn.close()

        if not token:
            return jsonify({
                'success': False,
                'error': '未找到对应的 Token，请检查 Key 是否正确'
            })

        # 计算总额度和剩余额度
        remain_quota = token['remain_quota'] or 0
        used_quota = token['used_quota'] or 0
        total_quota = remain_quota + used_quota

        # 过期时间处理
        expired_time = token['expired_time']
        expired_time_str = None
        if expired_time and expired_time != -1:
            expired_time_str = timestamp_to_datetime(expired_time)

        # 判断是否过期
        is_expired = False
        if expired_time and expired_time != -1:
            if datetime.now(tz=TZ_EAST_8).timestamp() > expired_time:
                is_expired = True

        return jsonify({
            'success': True,
            'data': {
                'key': mask_key(key),
                'full_key': key,  # 完整key仅用于后续查询
                'name': token['name'] or '未命名',
                'status': token['status'],
                'is_expired': is_expired,
                'expired_time': expired_time_str,
                'remain_quota': remain_quota,
                'used_quota': used_quota,
                'total_quota': total_quota,
                'remain_yuan': quota_to_yuan(remain_quota),
                'used_yuan': quota_to_yuan(used_quota),
                'total_yuan': quota_to_yuan(total_quota),
                'unlimited_quota': token['unlimited_quota'] or False,
                'exchange_rate': EXCHANGE_RATE
            }
        })

    except psycopg2.Error as e:
        return jsonify({
            'success': False,
            'error': f'数据库查询错误: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        })


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """
    获取调用日志
    参数：
        - key: API Key（必填）
        - time_range: 时间范围 today/yesterday/last_3_days/last_7_days/last_30_days
    - page: 页码
    - page_size: 每页条数
    """
    key = request.args.get('key', '').strip()
    time_range = request.args.get('time_range', 'last_7_days')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', DEFAULT_PAGE_SIZE, type=int)

    if not key:
        return jsonify({
            'success': False,
            'error': '请输入 API Key'
        })

    # 规范化Key：去掉sk-前缀
    normalized_key = normalize_key(key)

    # 限制page_size
    if page_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE
    if page < 1:
        page = 1

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 先通过key查询token的name（使用规范化的key）
        cur.execute("""
            SELECT name FROM tokens
            WHERE key = %s AND deleted_at IS NULL
        """, (normalized_key,))

        token = cur.fetchone()
        if not token:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': '未找到对应的 Token'
            })

        token_name = token['name']

        # 获取时间范围
        start_ts, end_ts = get_time_range_range(time_range)

        # 查询总数
        cur.execute("""
            SELECT COUNT(*) as total
            FROM logs
            WHERE token_name = %s
              AND created_at >= %s
              AND created_at <= %s
        """, (token_name, start_ts, end_ts))

        total = cur.fetchone()['total']

        # 查询日志列表
        offset = (page - 1) * page_size
        cur.execute("""
            SELECT created_at, model_name, prompt_tokens, completion_tokens,
                   quota, use_time, channel_name, ip
            FROM logs
            WHERE token_name = %s
              AND created_at >= %s
              AND created_at <= %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (token_name, start_ts, end_ts, page_size, offset))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        # 转换数据
        logs = []
        for row in rows:
            logs.append({
                'created_at': timestamp_to_datetime_str(row['created_at']),
                'model_name': row['model_name'] or '未知',
                'prompt_tokens': row['prompt_tokens'] or 0,
                'completion_tokens': row['completion_tokens'] or 0,
                'quota': row['quota'] or 0,
                'quota_yuan': quota_to_yuan(row['quota']),
                'use_time': (row['use_time'] or 0) / 1000.0 if row['use_time'] else 0,  # 转换为秒
                'channel_name': row['channel_name'] or '',
                'ip': row['ip'] or ''
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return jsonify({
            'success': True,
            'data': {
                'logs': logs,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            }
        })

    except psycopg2.Error as e:
        return jsonify({
            'success': False,
            'error': f'数据库查询错误: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    获取额度消耗统计
    参数：key - API Key
    """
    key = request.args.get('key', '').strip()

    if not key:
        return jsonify({
            'success': False,
            'error': '请输入 API Key'
        })

    # 规范化Key：去掉sk-前缀
    normalized_key = normalize_key(key)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 先查询token的name（使用规范化的key）
        cur.execute("""
            SELECT name FROM tokens
            WHERE key = %s AND deleted_at IS NULL
        """, (normalized_key,))

        token = cur.fetchone()
        if not token:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': '未找到对应的 Token'
            })

        token_name = token['name']

        # 统计各个时间范围的消耗
        ranges = {
            'today': 'today',
            'yesterday': 'yesterday',
            'last_3_days': 'last_3_days',
            'last_7_days': 'last_7_days',
            'last_30_days': 'last_30_days'
        }

        stats = {}
        for key_name, range_type in ranges.items():
            start_ts, end_ts = get_time_range_range(range_type)

            cur.execute("""
                SELECT COUNT(*) as count,
                       COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                       COALESCE(SUM(quota), 0) as quota
                FROM logs
                WHERE token_name = %s
                  AND created_at >= %s
                  AND created_at <= %s
            """, (token_name, start_ts, end_ts))

            row = cur.fetchone()
            stats[key_name] = {
                'count': row['count'] or 0,
                'prompt_tokens': row['prompt_tokens'] or 0,
                'completion_tokens': row['completion_tokens'] or 0,
                'quota': row['quota'] or 0,
                'quota_yuan': quota_to_yuan(row['quota'])
            }

        # 获取总统计（所有时间）
        cur.execute("""
            SELECT COUNT(*) as count,
                   COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                   COALESCE(SUM(quota), 0) as quota
            FROM logs
            WHERE token_name = %s
        """, (token_name,))

        row = cur.fetchone()
        stats['all'] = {
            'count': row['count'] or 0,
            'prompt_tokens': row['prompt_tokens'] or 0,
            'completion_tokens': row['completion_tokens'] or 0,
            'quota': row['quota'] or 0,
            'quota_yuan': quota_to_yuan(row['quota'])
        }

        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': stats
        })

    except psycopg2.Error as e:
        return jsonify({
            'success': False,
            'error': f'数据库查询错误: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        })


if __name__ == '__main__':
    from config import APP_HOST, APP_PORT, DEBUG
    app.run(host=APP_HOST, port=APP_PORT, debug=DEBUG)