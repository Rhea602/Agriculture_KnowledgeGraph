import requests
lst = []
import pandas as pd

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
    # 'Cookie': 'HWWAFSESID=6081073764a4d8fb2f; HWWAFSESTIME=1755082413865',
}
for page in range(1,384):
    print(page)
    json_data = {
        'croptype': [
            '粮食作物',
            '小麦',
        ],
        'p': {},
        'page': page,
        'limit': 100,
    }
    
    response = requests.post('https://www.cgris.net/cgris/query', cookies=cookies, headers=headers, json=json_data)
    
    sj_lst = response.json()['data']['list']
    lst.extend(sj_lst)
result = pd.DataFrame(lst)
result.to_excel('1.xlsx',index=None)