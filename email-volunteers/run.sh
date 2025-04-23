#!/bin/sh

export SSL_CERT_FILE=$(python3 -m certifi)
python3 main.py
