import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from tenacity import retry, stop_after_attempt, wait_fixed
from tqdm import tqdm

lst = []
error = []

cookies = {
    'HWWAFSESID': '6081073764a4d8fb2f',
    'HWWAFSESTIME': '1755082413865',
}

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Origin': 'https://www.cgris.net',
    'Pragma': 'no-cache',
    'Referer': 'https://www.cgris.net/detailSearch?name=%E5%B0%8F%E9%BA%A6&category=%E7%B2%AE%E9%A3%9F%E4%BD%9C%E7%89%A9',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0',
    'sec-ch-ua': '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

# 添加重试装饰器：最多重试3次，每次间隔1秒
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def craw(sid, pbar=None):
    try:
        json_data = {
            'croptype': [
                '粮食作物',
                '小麦',
            ],
            'p': sid,
        }
        
        response = requests.post(
            'https://www.cgris.net/cgris/item',
            cookies=cookies,
            headers=headers,
            json=json_data,
            timeout=10  # 添加超时设置
        )
        response.raise_for_status()  # 检查HTTP错误状态码
        
        sj_lst = response.json()['data']
        lst.append(sj_lst)
        return True
    except Exception as e:
        print(f"ID {sid} 错误: {str(e)}")
        raise  # 抛出异常让重试机制处理
    finally:
        if pbar:
            pbar.update(1)  # 更新进度条

if __name__ == "__main__":
    # 读取编号列表
    sid_lst = pd.read_excel('1.xlsx')['统一编号'].tolist()
    
    # 创建进度条
    with tqdm(total=len(sid_lst), desc="爬取进度") as pbar:
        # 使用线程池执行任务
        with ThreadPoolExecutor(3) as executor:
            # 提交所有任务并传递进度条引用
            futures = [executor.submit(craw, sid, pbar) for sid in sid_lst]
            
            # 等待所有任务完成并收集错误
            for future, sid in zip(futures, sid_lst):
                try:
                    future.result()
                except:
                    error.append(sid)
    
    # 保存结果
    result = pd.DataFrame(lst)
    result.to_excel('小麦.xlsx', index=None)
    
    # 保存错误ID
    if error:
        pd.DataFrame({'错误ID': error}).to_excel('错误ID.xlsx', index=None)
        print(f"爬取完成，共 {len(error)} 个ID爬取失败，已保存至错误ID.xlsx")
    else:
        print("全部爬取成功")