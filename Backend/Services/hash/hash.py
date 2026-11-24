"""Identificador estável e não reversível do IP usando HMAC-SHA256."""
import hmac
import ipaddress
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')


def encrypted(user_ip: str) -> str:
    secret_key = os.getenv('SECRET_KEY', '')
    if not secret_key.strip():
        raise ValueError('Defina SECRET_KEY no .env para identificar as conversas.')
    normalized_ip = ipaddress.ip_address(user_ip).compressed
    return hmac.new(secret_key.encode(), normalized_ip.encode(), digestmod='sha256').hexdigest()
