"""复现用户报告的 3 个端点 500 错误。"""
import json
import sys
import traceback

sys.path.insert(0, '.')
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# 先登录拿 token（如果有 seed 数据）
print('=' * 70)
print('GET /data-capabilities')
try:
    r = client.get('/api/v1/data-capabilities')
    print('  status:', r.status_code)
    if r.status_code >= 400:
        print('  body:', r.text[:2000])
except Exception as e:
    print('  EXC:', e)
    traceback.print_exc()

print('=' * 70)
print('GET /daily-brief')
try:
    r = client.get('/api/v1/daily-brief')
    print('  status:', r.status_code)
    if r.status_code >= 400:
        print('  body:', r.text[:2000])
except Exception as e:
    print('  EXC:', e)
    traceback.print_exc()

print('=' * 70)
print('GET /auth/personal-profile')
try:
    r = client.get('/api/v1/auth/personal-profile')
    print('  status:', r.status_code)
    if r.status_code >= 400:
        print('  body:', r.text[:2000])
except Exception as e:
    print('  EXC:', e)
    traceback.print_exc()