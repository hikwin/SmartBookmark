import json
import os
import re
from urllib.parse import urlparse
import database

# Fallback categories rules database if rules.json is missing or corrupted
DEFAULT_RULES = {
    "categories": [
        {
            "name": "🛠️ 开发工具",
            "hosts": ["github.com", "gitlab.com", "gitee.com", "bitbucket.org", "stackoverflow.com", "npmjs.com", "pypi.org", "docker.com", "maven.org", "vercel.app", "netlify.app", "jsrun.net", "codepen.io", "runoob.com", "w3schools.com"],
            "keywords": ["code", "dev", "developer", "programming", "api", "github", "git", "compiler", "debug", "console", "docs", "markdown", "json", "sql", "regex", "npm", "pip", "docker", "kubernetes", "k8s", "hosting", "server", "deploy", "database", "python", "javascript", "java", "golang", "rust", "c++", "html", "css", "开发", "代码", "编程", "程序员", "调试", "接口", "文档", "部署", "源码", "开源", "编译器", "数据库", "服务器", "云服务", "控制台", "算法", "极客", "解析"]
        },
        {
            "name": "📚 学习教育",
            "hosts": ["coursera.org", "udemy.com", "edx.org", "khanacademy.org", "arxiv.org", "wikipedia.org", "baike.baidu.com", "zhihu.com", "bilibili.com", "duolingo.com"],
            "keywords": ["learn", "study", "course", "tutorial", "book", "wiki", "math", "history", "physics", "science", "paper", "research", "academic", "dictionary", "dict", "translation", "translate", "english", "ielts", "toefl", "learning", "school", "university", "学习", "教程", "课程", "大学", "论文", "科研", "百科", "维基", "读书", "阅读", "英语", "考试", "题库", "备考", "词典", "翻译", "网课", "慕课", "公开课", "学术", "知乎"]
        },
        {
            "name": "🤖 人工智能",
            "hosts": ["openai.com", "chatgpt.com", "claude.ai", "anthropic.com", "deepseek.com", "huggingface.co", "midjourney.com", "coze.com", "poe.com"],
            "keywords": ["ai", "llm", "chatgpt", "gpt", "prompt", "claude", "gemini", "copilot", "model", "deepseek", "midjourney", "stable diffusion", "neural", "transformer", "agent", "artificial intelligence", "ollama", "huggingface", "人工智能", "大模型", "提示词", "智能体", "机器人", "神经网络", "深度学习", "机器学习"]
        },
        {
            "name": "🛒 购物电商",
            "hosts": ["amazon.com", "ebay.com", "aliexpress.com", "taobao.com", "jd.com", "tmall.com", "pinduoduo.com", "goofish.com", "meituan.com", "ele.me", "shopify.com", "smzdm.com"],
            "keywords": ["shop", "store", "buy", "mall", "price", "deal", "coupon", "cart", "checkout", "aliexpress", "amazon", "ebay", "order", "sale", "discount", "market", "pay", "购物", "电商", "淘宝", "京东", "拼多多", "闲鱼", "优惠", "省钱", "什么值得买", "团购", "外卖", "快递", "订单", "支付", "购物车", "海淘", "比价", "特价"]
        },
        {
            "name": "📰 新闻资讯",
            "hosts": ["bbc.com", "cnn.com", "reuters.com", "nytimes.com", "medium.com", "techcrunch.com", "36kr.com", "ithome.com", "jianshu.com", "csdn.net", "sspai.com", "cnbeta.com.tw"],
            "keywords": ["news", "daily", "blog", "feed", "article", "paper", "press", "journal", "newsletter", "rss", "report", "medium", "post", "magazine", "新闻", "资讯", "博客", "媒体", "周刊", "观察", "快讯", "深度", "简书", "少数派", "IT之家", "快报", "社论", "评论"]
        },
        {
            "name": "🎮 娱乐游戏",
            "hosts": ["steamcommunity.com", "steampowered.com", "epicgames.com", "itch.io", "twitch.tv", "netflix.com", "iqiyi.com", "v.qq.com", "spotify.com", "soundcloud.com", "music.163.com", "douyu.com", "huya.com", "youtube.com"],
            "keywords": ["game", "play", "video", "movie", "music", "anime", "comic", "live", "stream", "tv", "player", "song", "album", "audio", "podcast", "gaming", "steam", "epic", "switch", "playstation", "xbox", "nintendo", "游戏", "视频", "电影", "音乐", "动漫", "番剧", "直播", "娱乐", "听歌", "追剧", "网易云", "影视", "电台", "新番", "漫画"]
        },
        {
            "name": "💼 工作效率",
            "hosts": ["notion.so", "trello.com", "slack.com", "zoom.us", "office.com", "drive.google.com", "dropbox.com", "pan.baidu.com", "aliyundrive.com", "jianguoyun.com", "canva.com", "ilovepdf.com"],
            "keywords": ["tool", "work", "doc", "pdf", "email", "mail", "drive", "cloud", "calendar", "meeting", "task", "todo", "note", "efficiency", "sheet", "word", "excel", "ppt", "presentation", "project", "team", "collab", "management", "converter", "editor", "efficiency", "效率", "工具", "文档", "云盘", "网盘", "邮箱", "日历", "会议", "协同", "笔记", "转换", "表单", "看板", "管理", "脑图", "流程图", "在线编辑", "百度网盘", "阿里云盘"]
        },
        {
            "name": "🔒 安全防护",
            "hosts": ["hackerone.com", "exploit-db.com", "cve.mitre.org", "portswigger.net", "ctftime.org", "owasp.org", "freebuf.com", "anquanke.com"],
            "keywords": ["security", "hacker", "exploit", "vuln", "ctf", "malware", "decrypt", "encrypt", "bypass", "pentest", "firewall", "crypto", "cyber", "cve", "threat", "reverse", "decompile", "安全", "漏洞", "黑客", "渗透", "病毒", "逆向", "防护", "防范", "加密", "解密", "木马", "红队", "安全响应", "CTF", "信息安全"]
        },
        {
            "name": "🌐 社交网络",
            "hosts": ["twitter.com", "x.com", "facebook.com", "instagram.com", "reddit.com", "weibo.com", "tieba.baidu.com", "v2ex.com", "douban.com", "quora.com", "discord.com", "telegram.org"],
            "keywords": ["social", "chat", "community", "forum", "group", "share", "post", "reddit", "weibo", "discord", "telegram", "profile", "connect", "avatar", "tweet", "moment", "thread", "bbs", "社交", "微博", "论坛", "社区", "贴吧", "讨论", "朋友圈", "豆瓣", "群组", "部落", "交友"]
        },
        {
            "name": "💰 金融理财",
            "hosts": ["bloomberg.com", "finance.yahoo.com", "coinbase.com", "binance.com", "xueqiu.com", "eastmoney.com", "10jqka.com.cn", "jrj.com.cn"],
            "keywords": ["finance", "stock", "bank", "crypto", "coin", "invest", "wealth", "market", "trade", "bitcoin", "btc", "eth", "portfolio", "rate", "currency", "forex", "bonds", "股票", "基金", "理财", "金融", "银行", "证券", "投资", "币圈", "比特币", "以太坊", "行情", "雪球", "东方财富", "同花顺", "理财", "汇率", "炒股"]
        },
        {
            "name": "🎨 设计创意",
            "hosts": ["figma.com", "dribbble.com", "behance.net", "canva.com", "pinterest.com", "pixiv.net", "adobe.com", "unsplash.com", "iconfont.cn"],
            "keywords": ["design", "art", "image", "color", "photo", "font", "icon", "vector", "illustration", "3d", "ui", "ux", "canvas", "mockup", "creative", "portfolio", "gallery", "wallpaper", "sketch", "figma", "photoshop", "ps", "adobe", "设计", "素材", "图片", "配色", "字体", "图标", "矢量", "插画", "建模", "美化", "海报", "壁纸", "画师", "创意", "画廊"]
        },
        {
            "name": "✈️ 旅游出行",
            "hosts": ["maps.google.com", "map.baidu.com", "tripadvisor.com", "booking.com", "ctrip.com", "qunar.com", "airbnb.com", "amap.com"],
            "keywords": ["travel", "map", "hotel", "flight", "trip", "ticket", "booking", "route", "tour", "hostel", "navigation", "gps", "destination", "agency", "airline", "旅游", "出行", "地图", "酒店", "机票", "民宿", "攻略", "预订", "高德", "携程", "去哪儿", "自由行", "景点", "路线", "导航"]
        },
        {
            "name": "🏥 健康医疗",
            "hosts": ["webmd.com", "pubmed.ncbi.nlm.nih.gov", "dxy.cn", "guahao.com", "haodf.com"],
            "keywords": ["health", "medical", "doctor", "fitness", "medicine", "diet", "hospital", "clinic", "disease", "symptom", "pharmacy", "wellness", "workout", "gym", "健康", "医疗", "医生", "健身", "医药", "饮食", "医院", "挂号", "疾病", "症状", "诊所", "问诊", "丁香园", "医学"]
        },
        {
            "name": "🏠 本地局域网",
            "hosts": ["localhost", "127.0.0.1"],
            "keywords": ["lan", "local", "nas", "router", "intranet", "局域网", "内网", "本地", "路由器"]
        }
    ]
}

def load_rules(rules_path="rules.json"):
    """
    Load rule library from local rules.json. If missing or corrupted, returns DEFAULT_RULES.
    """
    if not os.path.exists(rules_path):
        return DEFAULT_RULES
    try:
        with open(rules_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "categories" in data and isinstance(data["categories"], list):
                return data
    except Exception:
        pass
    return DEFAULT_RULES

def is_local_or_intranet(host):
    if not host:
        return False
    host = host.split(":")[0]
    if host == "localhost" or host == "[::1]":
        return True
    if host.endswith(".local") or host.endswith(".lan") or host.endswith(".internal"):
        return True
    if "." not in host:
        if host and not host.isdigit():
            return True
            
    # Match Private IP patterns (127.x.x.x, 10.x.x.x, 172.16.x.x-172.31.x.x, 192.168.x.x)
    ip_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(ip_pattern, host)
    if match:
        try:
            parts = [int(p) for p in match.groups()]
            if all(0 <= p <= 255 for p in parts):
                p1, p2, p3, p4 = parts
                if p1 == 127:  # Loopback
                    return True
                if p1 == 10:   # Class A Private
                    return True
                if p1 == 172 and (16 <= p2 <= 31):  # Class B Private
                    return True
                if p1 == 192 and p2 == 168:  # Class C Private
                    return True
        except Exception:
            pass
    return False

def classify_bookmark(url, title, rules):
    """
    Classify a single bookmark URL and title using a weighted scoring model.
    """
    url_lower = url.lower()
    title_lower = title.lower()
    
    # Extract host
    try:
        parsed_url = urlparse(url)
        host = parsed_url.netloc.lower()
        if ":" in host:
            host = host.split(":")[0]
    except Exception:
        host = ""
        
    # Check if local/intranet address
    if is_local_or_intranet(host):
        return "🏠 本地局域网"
        
    best_category = "📦 其他"
    max_score = 0
    
    for cat in rules.get("categories", []):
        cat_name = cat.get("name", "")
        hosts = cat.get("hosts", [])
        keywords = cat.get("keywords", [])
        
        score = 0
        
        # 1. Host match (exact or suffix match, e.g., github.com matches wiki.github.com)
        for h in hosts:
            h_lower = h.lower()
            if host == h_lower or host.endswith("." + h_lower):
                score += 15  # Host matches have high priority
                break
                
        # 2. Keyword match (Title/URL keywords)
        for kw in keywords:
            kw_lower = kw.lower()
            # Local intranet category should not match title, only URL
            if "本地局域网" not in cat_name:
                if kw_lower in title_lower:
                    score += 3
            if kw_lower in url_lower:
                score += 1
                
        if score > max_score:
            max_score = score
            best_category = cat_name
            
    return best_category

def run_ai_classification(db_path, rules_path="rules.json"):
    """
    Reads bookmarks from database, classifies them, updates their categories in database.
    - Saves a version snapshot first so it can be undone.
    """
    rules = load_rules(rules_path)
    conn = database.get_db_connection(db_path)
    try:
        # Get list of unique URLs before operation to ensure no URL is lost
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM bookmarks")
        original_urls = [r['url'] for r in cursor.fetchall()]
        
        # Save snapshot
        database.save_version_snapshot(conn, "AI智能分类")
        
        cursor.execute("SELECT id, url, title FROM bookmarks")
        rows = cursor.fetchall()
        
        for r in rows:
            category = classify_bookmark(r['url'], r['title'], rules)
            cursor.execute("UPDATE bookmarks SET category = ? WHERE id = ?", (category, r['id']))
            
        conn.commit()
        
        # Verify integrity
        cursor.execute("SELECT url FROM bookmarks")
        new_urls = [r['url'] for r in cursor.fetchall()]
        missing = set(original_urls) - set(new_urls)
        if missing:
            conn.rollback()
            raise ValueError(f"AI分类后校验失败：有 {len(missing)} 个唯一网址丢失，已自动撤滚！")
            
        return len(rows)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
