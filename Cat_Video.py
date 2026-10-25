import requests
import time
import random
import json
from fake_useragent import UserAgent

class BilibiliCrawler:
    def __init__(self):
        self.ua = UserAgent()
        self.timeout = 10
        self.max_retries = 3
        self.success_count = 0
        self.fail_count = 0
        self.is_banned = False
        
    def search_videos(self, keyword, page=1):
        if self.is_banned:
            return None
            
        url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": page
        }

        for attempt in range(self.max_retries):
            headers = {
                'User-Agent': self.ua.random,
                'Referer': 'https://www.bilibili.com/',
                'Origin': 'https://www.bilibili.com',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }

            delay = random.uniform(3 + attempt * 2, 6 + attempt * 3)
            print(f"等待 {delay:.1f} 秒后发起请求，第 {attempt + 1} 次尝试")
            time.sleep(delay)

            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )

                print(f"状态码: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"第 {page} 页搜索成功")
                    self.success_count += 1
                    return response.json()
                    
                elif response.status_code == 412:
                    print("被B站限制访问，停止爬取")
                    self.is_banned = True
                    return None
                    
                elif response.status_code == 404:
                    print("页面不存在，可能是最后一页")
                    return None
                    
                else:
                    print(f"请求失败，状态码: {response.status_code}")
                    print(f"返回内容: {response.text[:200]}")
                    time.sleep(20)
                    continue

            except requests.exceptions.Timeout:
                print("请求超时，重试中")
                time.sleep(10)
                continue
                
            except requests.exceptions.ConnectionError:
                print("连接错误，检查网络")
                time.sleep(15)
                continue
                
            except Exception as e:
                print(f"请求异常: {e}")
                time.sleep(10)
                continue
        
        self.fail_count += 1
        print(f"第 {page} 页所有重试均失败")
        return None

    def save_results(self, videos, filename="bilibili_meme_series.json"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(videos, f, ensure_ascii=False, indent=2)
            print(f"数据已保存到 {filename}")
        except Exception as e:
            print(f"保存失败: {e}")

    def print_video_info(self, video):
        title = video.get('title', '无标题')
        title = title.replace('<em class="keyword">', '').replace('</em>', '')
        bvid = video.get('bvid', '无BV号')
        author = video.get('author', '未知UP主')
        view = video.get('view', 0)
        danmaku = video.get('danmaku', 0)
        like = video.get('like', 0)
        duration = video.get('duration', '未知')
        pubdate = video.get('pubdate', '未知')
        
        print(f"标题: {title}")
        print(f"BV号: {bvid}")
        print(f"UP主: {author}")
        print(f"时长: {duration} 秒")
        print(f"播放: {view}")
        print(f"弹幕: {danmaku}")
        print(f"点赞: {like}")
        if isinstance(pubdate, int):
            print(f"发布时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(pubdate))}")
        print("")

if __name__ == "__main__":
    print("B站Meme合集视频爬虫启动")
    print("=" * 60)
    
    crawler = BilibiliCrawler()
    
    # 搜索带编号的meme合集
    KEYWORDS = [
        "meme #",
        "MeMes #",
        "梗 #",
        "合集 meme",
        "meme 合集 编号",
        "每日 meme",
    ]
    MAX_PAGES_PER_KEYWORD = 2
    SAVE_DATA = True
    
    all_videos = []
    
    for keyword in KEYWORDS:
        print(f"\n搜索关键词: {keyword}")
        print("=" * 60)
        
        for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
            if crawler.is_banned:
                print("检测到限制状态，程序已停止")
                break
                
            print(f"\n正在爬取第 {page} 页")
            print("-" * 60)
            
            result = crawler.search_videos(keyword, page)
            
            if crawler.is_banned:
                print("检测到限制状态，程序已停止")
                break
            
            if result and result.get('data'):
                video_list = result['data'].get('result', [])
                
                if not video_list:
                    print(f"关键词 '{keyword}' 第 {page} 页没有更多视频")
                    break
                    
                print(f"\n第 {page} 页找到 {len(video_list)} 个视频")
                print("-" * 60)
                
                for v in video_list:
                    crawler.print_video_info(v)
                    all_videos.append(v)
                
            else:
                print(f"第 {page} 页获取失败，停止爬取")
                break
            
            if page < MAX_PAGES_PER_KEYWORD:
                wait = random.uniform(20, 40)
                print(f"等待 {wait:.1f} 秒后爬取下一页")
                print("-" * 60)
                time.sleep(wait)
        
        if keyword != KEYWORDS[-1] and not crawler.is_banned:
            wait = random.uniform(30, 60)
            print(f"\n切换关键词，等待 {wait:.1f} 秒")
            time.sleep(wait)
    
    print("\n" + "=" * 60)
    
    if crawler.is_banned:
        print("程序因被限制而停止")
    else:
        print("爬取完成")
        
    print(f"成功页数: {crawler.success_count}")
    print(f"失败页数: {crawler.fail_count}")
    print(f"获取视频总数: {len(all_videos)}")
    
    if SAVE_DATA and all_videos:
        crawler.save_results(all_videos)
        
    print("=" * 60)
    print("程序结束")
