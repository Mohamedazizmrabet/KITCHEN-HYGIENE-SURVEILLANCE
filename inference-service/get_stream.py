import urllib.request
import re

url = "https://open.ivideon.com/embed/v2/?server=100-3f1933bc335aed64e3a0a0ead67bca0e&camera=0&lang=en"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    m = re.search(r'https://[^"]+\.m3u8[^"]*', html)
    if m:
        print("M3U8:", m.group(0))
    else:
        print("No m3u8 found.")
        m = re.search(r'https://[^"]+\.flv[^"]*', html)
        if m:
            print("FLV:", m.group(0))
except Exception as e:
    print(e)
