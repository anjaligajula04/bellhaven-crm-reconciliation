import os
from dotenv import load_dotenv

load_dotenv()

CRM_API_BASE = os.getenv("CRM_API_BASE")
CRM_API_TOKEN = os.getenv("CRM_API_TOKEN")
WEBSITE_BASE = os.getenv("WEBSITE_BASE")

if not CRM_API_BASE:
    raise ValueError("CRM_API_BASE is missing from .env")

if not CRM_API_TOKEN:
    raise ValueError("CRM_API_TOKEN is missing from .env")

if not WEBSITE_BASE:
    raise ValueError("WEBSITE_BASE is missing from .env")