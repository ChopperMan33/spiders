'''
@Author: gunjianpan
@Date:   2019-04-20 15:04:03
@Last Modified by:   gunjianpan
@Last Modified time: 2019-04-20 21:13:19
'''

import numpy as np
import platform
import re
import requests
import threading
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOMEPAGE_URL = 'https://www.dytt8.net'
#修改header 模拟浏览器访问
headers = {
    'sec-ch-ua': 'Google Chrome 76',
    'Sec-Fetch-Dest': 'script',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3771.0 Safari/537.36'}
html_timeout = 10
start = []
movie_list = []
movie_another = []
failure_map = {}
movie_again = []

#由于使用了代理，所以重试三次防止不成功的情况出现
def can_retry(url: str, index=None) -> bool:
    ''' judge can retry once '''
    global failure_map
    if url not in failure_map:
        failure_map[url] = 0
        return True
    elif failure_map[url] < 2:
        failure_map[url] += 1
        return True
    else:
        failure_map[url] = 0
        return False


def echo(color, *args, is_service=False):
    ''' echo log @param: color: 0 -> error, 1 -> success, 2 -> info '''
    if is_service:
        return
    colors = {'error': '\033[91m', 'success': '\033[94m', 'info': '\033[93m'}
    args = ' '.join([str(ii) for ii in args])
    if type(color) != int or not color in list(range(len(colors.keys()))) or platform.system() == 'Windows':
        print(args)
    else:
        print(list(colors.values())[color], args, '\033[0m')

#按块启动多线程
def shuffle_batch_run_thread(threading_list: list, batch_size=24):
    ''' shuffle batch run thread '''
    thread_num = len(threading_list)
    np.random.shuffle(threading_list)  # shuffle thread
    for block in range(thread_num // batch_size + 1):
        for ii in threading_list[block * batch_size:min(thread_num, batch_size * (block + 1))]:
            ii.start()
        for ii in threading_list[block * batch_size:min(thread_num, batch_size * (block + 1))]:
            ii.join()

#记录起止时间
def begin_time() -> int:
    ''' multi-version time manage '''
    global start
    start.append(time.time())
    return len(start) - 1

def end_time(version: int, mode: int = 1):
    time_spend = time.time() - start[version]
    if mode:
        echo(2, '{:.3f}s'.format(time_spend))
    else:
        return time_spend

#动态修改header的referer为当前请求的url，用try-except报错返回一个空字符串，encoding = 'GB2312'，使用代理
def get_text(url: str, proxies=None, header=None) -> str:
    ''' get text '''
    if header is None:
        header = headers
        header['Referer'] = url
    try:
        req = requests.get(url, headers=header, verify=False,
                           timeout=html_timeout, proxies=proxies)
        ''' change encoding '''
        req.encoding = 'GB2312'
        return req.text
    except:
        return ''

#请求首页
def load_index():
    ''' load index '''
    global movie_list
    version = begin_time()
    text = get_text(HOMEPAGE_URL)
    #爬取首页电影，共95条
    movie_list = re.findall('《(.*?)》', text)
    #提取“更多”标签对应的url，并依次遍历
    movie_more = re.findall('href="(.*?)">更多', text)
    for uri in movie_more:
        load_other(uri)

    #使用多线程加速请求的分页
    threading_list = [threading.Thread(
        target=load_other, args=(ii,)) for ii in movie_another]
    shuffle_batch_run_thread(threading_list, 100)
    threading_list = [threading.Thread(
        target=load_other, args=(ii,)) for ii in movie_again]
    shuffle_batch_run_thread(threading_list, 100)
    #去重复
    movie_list = set(movie_list)
    out_path = 'dytt8_result.txt'
    #导出爬取的 电影列表至txt文件
    with open(out_path, 'w') as f:
        f.write('\n'.join(movie_list))
    url_num = len([*movie_more, *movie_another]) + 1
    movie_num = len(movie_list)
    echo(1, 'Requests num: {}\nMovie num: {}\nOutput path: {}\nSpend time: {:.2f}s\n'.format(
            url_num, movie_num, out_path, end_time(version, 0)))

#请求具体页面，获取页面所有电影信息，和所有分页的url
def load_other(uri):
    ''' load other '''
    global movie_list, movie_another, movie_again
    url = HOMEPAGE_URL + uri if not 'http' in uri else uri
    text = get_text(url)

    temp_list = re.findall('《(.*?)》', text)
    echo(2, 'loading', url, 'movie num:', len(temp_list), 'Failure time',
         failure_map[url] + 1 if url in failure_map else 0)

    if text == '' or not len(temp_list):
        if can_retry(url):
            load_other(uri)
        else:
            movie_again.append(url)
        return
    if 'index' in url and '共' in text:
        total_page = re.findall('共(.*?)页', text)[0]
        suffix_str = re.findall(r"value=\'(.*?)1.html\' selected", text)[0]
        more_movie = [url.replace('index.html', '{}{}.html'.format(
            suffix_str, ii)) for ii in range(2, int(total_page) + 1)]
    else:
        more_movie = []
    movie_list += temp_list
    movie_another += more_movie


if __name__ == '__main__':
    load_index()
