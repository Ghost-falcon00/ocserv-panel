"""
System Settings Model
مدل تنظیمات سیستم - کامل با تمام تنظیمات OCServ
"""

from sqlalchemy import Column, Integer, String, Text
from .database import Base


class SystemSettings(Base):
    """
    مدل تنظیمات سیستم
    ذخیره تنظیمات key-value
    """
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)  # توضیحات فارسی
    category = Column(String(50), default="general")  # دسته‌بندی
    config_key = Column(String(100), nullable=True)  # نام واقعی در فایل کانفیگ
    value_type = Column(String(20), default="string")  # string, number, boolean
    
    def __repr__(self):
        return f"<Setting {self.key}={self.value}>"


# تنظیمات کامل OCServ با توضیحات فارسی
DEFAULT_SETTINGS = {
    # ═══════════════════════════════════════════════════════════
    # تنظیمات شبکه (Network)
    # ═══════════════════════════════════════════════════════════
    "tcp_port": {
        "value": "4443",
        "description": "پورت TCP برای اتصال - پیشنهاد: 443 یا 4443",
        "category": "network",
        "config_key": "tcp-port",
        "value_type": "number"
    },
    "udp_port": {
        "value": "4443",
        "description": "پورت UDP برای DTLS - سرعت بالاتر با UDP",
        "category": "network",
        "config_key": "udp-port",
        "value_type": "number"
    },
    "ipv4_network": {
        "value": "192.168.100.0",
        "description": "آدرس شبکه داخلی VPN - مثال: 192.168.100.0",
        "category": "network",
        "config_key": "ipv4-network",
        "value_type": "string"
    },
    "ipv4_netmask": {
        "value": "255.255.255.0",
        "description": "ماسک شبکه - معمولاً 255.255.255.0",
        "category": "network",
        "config_key": "ipv4-netmask",
        "value_type": "string"
    },
    "dns1": {
        "value": "1.1.1.1",
        "description": "DNS اول - پیشنهاد: 1.1.1.1 (کلودفلر - سریع‌ترین)",
        "category": "network",
        "config_key": "dns",
        "value_type": "string"
    },
    "dns2": {
        "value": "8.8.8.8", 
        "description": "DNS دوم - پیشنهاد: 8.8.8.8 (گوگل)",
        "category": "network",
        "config_key": "dns",
        "value_type": "string"
    },
    "tunnel_all_dns": {
        "value": "true",
        "description": "تمام ترافیک DNS از VPN برود - برای دور زدن فیلترینگ ضروری",
        "category": "network",
        "config_key": "tunnel-all-dns",
        "value_type": "boolean"
    },
    
    # ═══════════════════════════════════════════════════════════
    # تنظیمات اتصال (Connection)
    # ═══════════════════════════════════════════════════════════
    "max_clients": {
        "value": "128",
        "description": "حداکثر تعداد کل کاربران همزمان روی سرور",
        "category": "connection",
        "config_key": "max-clients",
        "value_type": "number"
    },
    "max_same_clients": {
        "value": "4",
        "description": "حداکثر اتصال همزمان برای هر کاربر (تعداد دستگاه)",
        "category": "connection",
        "config_key": "max-same-clients",
        "value_type": "number"
    },
    "keepalive": {
        "value": "32400",
        "description": "فاصله Keep-Alive (ثانیه) - مقدار بالا برای ایران بهتره",
        "category": "connection",
        "config_key": "keepalive",
        "value_type": "number"
    },
    "dpd": {
        "value": "90",
        "description": "Dead Peer Detection - تشخیص قطعی اتصال (ثانیه)",
        "category": "connection",
        "config_key": "dpd",
        "value_type": "number"
    },
    "mobile_dpd": {
        "value": "1800",
        "description": "DPD برای موبایل - مقدار بیشتر برای صرفه‌جویی باتری",
        "category": "connection",
        "config_key": "mobile-dpd",
        "value_type": "number"
    },
    "switch_to_tcp_timeout": {
        "value": "25",
        "description": "زمان سوییچ از UDP به TCP در صورت عدم پاسخ",
        "category": "connection",
        "config_key": "switch-to-tcp-timeout",
        "value_type": "number"
    },
    "idle_timeout": {
        "value": "1200",
        "description": "زمان قطع در صورت بیکار بودن (ثانیه) - 0 = غیرفعال",
        "category": "connection",
        "config_key": "idle-timeout",
        "value_type": "number"
    },
    "mobile_idle_timeout": {
        "value": "2400",
        "description": "زمان قطع بیکاری برای موبایل - بیشتر از دسکتاپ",
        "category": "connection",
        "config_key": "mobile-idle-timeout",
        "value_type": "number"
    },
    
    # ═══════════════════════════════════════════════════════════
    # تنظیمات امنیتی (Security)
    # ═══════════════════════════════════════════════════════════
    "auth_timeout": {
        "value": "240",
        "description": "مهلت احراز هویت (ثانیه)",
        "category": "security",
        "config_key": "auth-timeout",
        "value_type": "number"
    },
    "cookie_timeout": {
        "value": "300",
        "description": "مدت اعتبار کوکی session (ثانیه)",
        "category": "security",
        "config_key": "cookie-timeout",
        "value_type": "number"
    },
    "rekey_time": {
        "value": "172800",
        "description": "فاصله تعویض کلید رمزنگاری (ثانیه) - پیش‌فرض: 2 روز",
        "category": "security",
        "config_key": "rekey-time",
        "value_type": "number"
    },
    "rekey_method": {
        "value": "ssl",
        "description": "روش تعویض کلید - ssl یا new-tunnel",
        "category": "security",
        "config_key": "rekey-method",
        "value_type": "string"
    },
    "min_reauth_time": {
        "value": "300",
        "description": "حداقل زمان بین احراز هویت مجدد",
        "category": "security",
        "config_key": "min-reauth-time",
        "value_type": "number"
    },
    "max_ban_score": {
        "value": "80",
        "description": "امتیاز برای بن شدن IP - محافظت در برابر حمله",
        "category": "security",
        "config_key": "max-ban-score",
        "value_type": "number"
    },
    "ban_reset_time": {
        "value": "1200",
        "description": "زمان ریست شدن بن (ثانیه)",
        "category": "security",
        "config_key": "ban-reset-time",
        "value_type": "number"
    },
    "deny_roaming": {
        "value": "false",
        "description": "جلوگیری از تغییر IP در حین اتصال - false برای موبایل بهتره",
        "category": "security",
        "config_key": "deny-roaming",
        "value_type": "boolean"
    },
    "tls_priorities": {
        "value": "PERFORMANCE:%SERVER_PRECEDENCE:%COMPAT:-VERS-SSL3.0:-VERS-TLS1.0",
        "description": "اولویت‌های TLS - این تنظیم بهینه برای سرعت و امنیته",
        "category": "security",
        "config_key": "tls-priorities",
        "value_type": "string"
    },
    
    # ═══════════════════════════════════════════════════════════
    # تنظیمات عملکرد (Performance)
    # ═══════════════════════════════════════════════════════════
    "output_buffer": {
        "value": "23000",
        "description": "اندازه بافر خروجی (bytes) - تأثیر زیاد روی سرعت",
        "category": "performance",
        "config_key": "output-buffer",
        "value_type": "number"
    },
    "try_mtu_discovery": {
        "value": "true",
        "description": "تلاش برای کشف MTU بهینه - پیشنهاد: فعال",
        "category": "performance",
        "config_key": "try-mtu-discovery",
        "value_type": "boolean"
    },
    "mtu": {
        "value": "1400",
        "description": "حداکثر اندازه پکت - کمتر از 1500 برای پایداری بهتر",
        "category": "performance",
        "config_key": "mtu",
        "value_type": "number"
    },
    "compression": {
        "value": "true",
        "description": "فشرده‌سازی ترافیک - می‌تونه سرعت رو بالا ببره",
        "category": "performance",
        "config_key": "compression",
        "value_type": "boolean"
    },
    "no_compress_limit": {
        "value": "256",
        "description": "حداقل اندازه پکت برای فشرده‌سازی",
        "category": "performance",
        "config_key": "no-compress-limit",
        "value_type": "number"
    },
    
    # ═══════════════════════════════════════════════════════════
    # سازگاری (Compatibility)
    # ═══════════════════════════════════════════════════════════
    "cisco_client_compat": {
        "value": "true",
        "description": "سازگاری با کلاینت‌های Cisco AnyConnect - ضروری",
        "category": "compatibility",
        "config_key": "cisco-client-compat",
        "value_type": "boolean"
    },
    "dtls_legacy": {
        "value": "true",
        "description": "پشتیبانی از DTLS قدیمی - برای کلاینت‌های قدیمی‌تر",
        "category": "compatibility",
        "config_key": "dtls-legacy",
        "value_type": "boolean"
    },
    "isolate_workers": {
        "value": "true",
        "description": "جداسازی پردازش‌ها - امنیت بالاتر",
        "category": "compatibility",
        "config_key": "isolate-workers",
        "value_type": "boolean"
    },
    "predictable_ips": {
        "value": "true",
        "description": "IP ثابت برای هر کاربر - مفید برای ردیابی",
        "category": "compatibility",
        "config_key": "predictable-ips",
        "value_type": "boolean"
    },
}


# دسته‌بندی‌ها با نام فارسی
SETTING_CATEGORIES = {
    "network": "شبکه",
    "connection": "اتصال",
    "security": "امنیت",
    "performance": "عملکرد",
    "compatibility": "سازگاری"
}
