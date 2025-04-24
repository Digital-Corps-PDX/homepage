:: https://stackoverflow.com/a/2340018/246801
for /f %%i in ('python3 -m certifi') do set SSL_CERT_FILE=%%i
python3 main.py
