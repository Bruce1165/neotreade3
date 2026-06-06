#!/usr/bin/env python3
"""
补采 202#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/st#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code,#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks
#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code,#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['kl#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[3]),
                    'low': float(fields#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[3]),
                    'low': float(fields[4]),
                    'volume': float(fields[5]),
                    'amount':#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[3]),
                    'low': float(fields[4]),
                    'volume': float(fields[5]),
                    'amount': float(fields[6]),
                    'pct_change': float(fields[8]),
                }
    except Exception as e:
#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[3]),
                    'low': float(fields[4]),
                    'volume': float(fields[5]),
                    'amount': float(fields[6]),
                    'pct_change': float(fields[8]),
                }
    except Exception as e:
        print(f"  获取 {code} 失败: {e}")
    
#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[3]),
                    'low': float(fields[4]),
                    'volume': float(fields[5]),
                    'amount': float(fields[6]),
                    'pct_change': float(fields[8]),
                }
    except Exception as e:
        print(f"  获取 {code} 失败: {e}")
    
    return None

def insert_daily_prices(records):
    """批量插入日线#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[3]),
                    'low': float(fields[4]),
                    'volume': float(fields[5]),
                    'amount': float(fields[6]),
                    'pct_change': float(fields[8]),
                }
    except Exception as e:
        print(f"  获取 {code} 失败: {e}")
    
    return None

def insert_daily_prices(records):
    """批量插入日线数据"""
    if not records:
        return 0
    
#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用东方财富历史K线接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 东方财富接口
EASTMONEY_API_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

def get_stock_list():
    """从数据库获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, market FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    stocks = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock_data_eastmoney(code, market, date_str):
    """使用东方财富接口获取单只股票的历史数据"""
    # market: 1=上海, 0=深圳
    secid = f"{market}.{code}"
    url = f"{EASTMONEY_API_URL}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&beg={date_str}&end={date_str}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('data') and data['data'].get('klines') and len(data['data']['klines']) > 0:
                kline = data['data']['klines'][0]
                # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                fields = kline.split(',')
                return {
                    'code': code,
                    'trade_date': fields[0],
                    'open': float(fields[1]),
                    'close': float(fields[2]),
                    'high': float(fields[3]),
                    'low': float(fields[4]),
                    'volume': float(fields[5]),
                    'amount': float(fields[6]),
                    'pct_change': float(fields[8]),
                }
    except Exception as e:
        print(f"  获取 {code} 失败: {e}")
    
    return None

def insert_daily_prices(records):
    """批量插入日线数据"""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
