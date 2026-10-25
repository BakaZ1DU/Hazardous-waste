import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get("https://movie.douban.com/top250", headers=headers)

print("状态码:", response.status_code)
if response.status_code == 200:
    print("访问成功")
    print("网页200字符:", response.text[:200])
else:
    print("访问失败:", response.status_code)
print(response.text) 
 
