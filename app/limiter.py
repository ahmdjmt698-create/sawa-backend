"""
مثيل واحد مشترك لـ Rate Limiter — يُستخدم في كل أرجاء التطبيق
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
