import urllib.request
import os

url_prelim = 'ftp://ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/PRELIM/ACGRBR25.dbc'
url_finais = 'ftp://ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/FINAIS/ACGRBR25.dbc'

for url in [url_prelim, url_finais]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            info = response.info()
            print(f"Found at {url}")
            print(f"Size: {info.get_all('Content-Length')}")
            print(f"Last-Modified: {info.get_all('Last-Modified')}")
    except Exception as e:
        print(f"Failed for {url}: {e}")
