import requests
from bs4 import BeautifulSoup
import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from tqdm import tqdm
import os
from datetime import datetime

# 创建线程安全的列表
class ThreadSafeList:
    def __init__(self):
        self._list = []
        self._lock = Lock()
    
    def append(self, item):
        with self._lock:
            self._list.append(item)
    
    def __len__(self):
        return len(self._list)
    
    def get_list(self):
        return self._list

# 处理单个视频链接的函数
def process_video_link(args):
    link, i, total = args
    video_title = link.text.strip()
    
    try:
        match = re.search(r'id/(\d+)', link['href'])
        if match:
            video_id = match.group(1)
            play_url = f"https://xaavv.xyz/vod/play/id/{video_id}/sid/1/nid/1.html"

            play_response = requests.get(play_url)
            play_soup = BeautifulSoup(play_response.content, 'html.parser')

            script_tags = play_soup.find_all('script')
            for script in script_tags:
                if script.string and 'player_aaaa' in script.string:
                    match_url = re.search(r'"url":\s*"([^"]+)"', script.string)
                    if match_url:
                        m3u8_path = match_url.group(1).replace('\\/', '/')
                        if m3u8_path.startswith('/m3/'):
                            m3u8_url = f"https://cdn.xaavv.xyz{m3u8_path}"
                            return (True, video_title, m3u8_url, None)

            return (False, video_title, play_url, "无法获取下载地址")
    except Exception as e:
        return (False, video_title, play_url if 'play_url' in locals() else None, str(e))

# 设置页码范围：默认 1-29
page_range = list(range(1, 30))

videos = ThreadSafeList()
failed_videos = ThreadSafeList()
total_videos = 0

with ThreadPoolExecutor(max_workers=5) as executor:
    for page_num in page_range:
        if page_num == 1:
            url = "https://xaavv.xyz/vod/type/id/7.html"
        else:
            url = f"https://xaavv.xyz/vod/type/id/7/page/{page_num}.html"

        print(f"\n正在抓取第 {page_num} 页：{url}")
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            video_links = soup.find_all('a', class_='title text-sub-title mt-2 mb-3')
            total_videos += len(video_links)

            tasks = [(link, i, len(video_links)) for i, link in enumerate(video_links, 1)]
            
            with tqdm(total=len(video_links), desc=f"第{page_num}页进度") as pbar:
                futures = [executor.submit(process_video_link, task) for task in tasks]
                for future in futures:
                    success, title, url, error = future.result()
                    if success:
                        videos.append((title, url, page_num))
                    else:
                        failed_videos.append((title, url))
                    pbar.update(1)

            time.sleep(1)
        except Exception as e:
            print(f"抓取页面出错：{str(e)}")
            continue

print(f"\n=== 下载任务完成 ===")
print(f"总计发现视频：{total_videos} 个")
print(f"成功获取链接：{len(videos)} 个")
print(f"获取失败：{len(failed_videos)} 个\n")

history_folder = 'history'
if not os.path.exists(history_folder):
    os.makedirs(history_folder)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_filename = f'video_links_page1-29_{timestamp}.txt'
output_path = os.path.join(history_folder, output_filename)

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(f"总计发现视频：{total_videos} 个\n")
    f.write(f"成功获取链接：{len(videos)} 个\n")
    f.write(f"获取失败：{len(failed_videos)} 个\n\n")
    
    f.write("=== 成功获取的链接 ===\n")
    for title, url, page_num in videos.get_list():
        clean_title = title.replace(' ', '').replace('\t', '').replace('\n', '')
        f.write(f"{url} {clean_title} 第{page_num}页\n")
    
    if len(failed_videos) > 0:
        f.write("\n=== 获取失败的视频 ===\n")
        for title, url in failed_videos.get_list():
            f.write(f"【{title}】=> {url}\n")

print(f"所有链接已保存到 {output_filename} 文件中")
