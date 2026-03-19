# -*- coding: utf-8 -*-
"""
Skill: weather.query
天气查询 — 使用 Open-Meteo API（完全免费、无需 Key）。

架构：
- Open-Meteo Geocoding API: 城市名 → 经纬度（支持中文）
- Open-Meteo Forecast API:  经纬度 → 当前天气 + 当日预报
- 内置常用城市坐标缓存，减少 Geocoding 请求
"""
import sys
import requests
from config import WEATHER_CITY

# ============ WMO Weather Code → 中文描述 ============
_WMO_CODES = {
    0: "晴", 1: "大部晴朗", 2: "多云", 3: "阴天",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "大冻雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    77: "雪粒", 80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷暴", 96: "雷暴伴冰雹", 99: "强雷暴伴冰雹",
}

# ============ 常用城市坐标缓存（避免频繁调用 Geocoding）============
_CITY_COORDS = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737),
    "深圳": (22.5431, 114.0579), "广州": (23.1291, 113.2644),
    "杭州": (30.2741, 120.1551), "成都": (30.5728, 104.0668),
    "武汉": (30.5928, 114.3055), "南京": (32.0603, 118.7969),
    "重庆": (29.5630, 106.5516), "西安": (34.2658, 108.9541),
    "苏州": (31.2990, 120.5853), "天津": (39.1235, 117.1950),
    "长沙": (28.2282, 112.9388), "郑州": (34.7466, 113.6253),
    "青岛": (36.0671, 120.3826), "大连": (38.9140, 121.6147),
    "厦门": (24.4798, 118.0894), "珠海": (22.2710, 113.5767),
    "佛山": (23.0218, 113.1218), "东莞": (23.0208, 113.7518),
    "昆明": (25.0389, 102.7183), "合肥": (31.8206, 117.2272),
    "福州": (26.0745, 119.2965), "济南": (36.6512, 116.9972),
    "沈阳": (41.8057, 123.4315), "哈尔滨": (45.8038, 126.5350),
    "长春": (43.8171, 125.3235), "石家庄": (38.0428, 114.5149),
    "南宁": (22.8170, 108.3665), "贵阳": (26.6470, 106.6302),
    "太原": (37.8706, 112.5489), "兰州": (36.0611, 103.8343),
    "海口": (20.0440, 110.1999), "银川": (38.4872, 106.2309),
    "西宁": (36.6171, 101.7782), "拉萨": (29.6500, 91.1000),
    "乌鲁木齐": (43.8256, 87.6168), "呼和浩特": (40.8422, 111.7500),
    "三亚": (18.2528, 109.5120), "中山": (22.5176, 113.3929),
    "惠州": (23.1116, 114.4161), "香港": (22.3193, 114.1694),
    "澳门": (22.1987, 113.5439), "台北": (25.0330, 121.5654),
    # 常用国际城市
    "东京": (35.6762, 139.6503), "首尔": (37.5665, 126.9780),
    "新加坡": (1.3521, 103.8198), "曼谷": (13.7563, 100.5018),
    "纽约": (40.7128, -74.0060), "伦敦": (51.5074, -0.1278),
    "巴黎": (48.8566, 2.3522), "悉尼": (-33.8688, 151.2093),
    "洛杉矶": (34.0522, -118.2437), "旧金山": (37.7749, -122.4194),
    "温哥华": (49.2827, -123.1207), "多伦多": (43.6532, -79.3832),
    "柏林": (52.5200, 13.4050), "莫斯科": (55.7558, 37.6173),
    "迪拜": (25.2048, 55.2708), "吉隆坡": (3.1390, 101.6869),
}


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _geocode(city: str) -> tuple:
    """
    城市名 → (lat, lon, resolved_name)
    优先查本地缓存，miss 时调 Open-Meteo Geocoding API。
    """
    # 本地缓存命中
    if city in _CITY_COORDS:
        lat, lon = _CITY_COORDS[city]
        return lat, lon, city

    # 调 Geocoding API（先中文，再英文 fallback）
    for lang in ("zh", "en"):
        try:
            resp = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": lang},
                timeout=5
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    r = results[0]
                    name = r.get("name", city)
                    lat, lon = r["latitude"], r["longitude"]
                    # 写入运行时缓存
                    _CITY_COORDS[city] = (lat, lon)
                    _log(f"[weather] geocode: {city} → {name} ({lat}, {lon}) [lang={lang}]")
                    return lat, lon, name
        except Exception as e:
            _log(f"[weather] geocode 失败 [{lang}]: {city} — {e}")

    _log(f"[weather] geocode 无结果: {city}")
    return None, None, city


def fetch_weather(city: str = None, _retries: int = 3) -> dict:
    """
    统一天气获取函数（供 skill handler 和 app.py morning_report 调用）。

    内置重试机制：遇到 5xx / 超时 / 网络错误自动重试（默认 3 次，间隔递增）。

    返回 dict 或 None:
        city, weather_desc, high, low, feels_like, humidity,
        wind_speed_kmph, uv_index, rain_chance, sunrise, sunset
    """
    import time as _time

    city = city or WEATHER_CITY or "北京"
    lat, lon, resolved_name = _geocode(city)
    if lat is None:
        return None

    last_err = None
    for attempt in range(1, _retries + 1):
        try:
            resp = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": ",".join([
                        "temperature_2m", "relative_humidity_2m",
                        "apparent_temperature", "weather_code",
                        "wind_speed_10m",
                    ]),
                    "daily": ",".join([
                        "weather_code", "temperature_2m_max", "temperature_2m_min",
                        "precipitation_probability_max", "uv_index_max",
                        "sunrise", "sunset",
                    ]),
                    "timezone": "auto",
                    "forecast_days": 1,
                },
                timeout=10
            )

            # 5xx 可重试
            if resp.status_code >= 500:
                _log(f"[weather] Open-Meteo 返回 {resp.status_code} (尝试 {attempt}/{_retries})")
                last_err = f"HTTP {resp.status_code}"
                if attempt < _retries:
                    _time.sleep(attempt * 2)  # 2s, 4s 递增
                    continue
                return None

            if resp.status_code != 200:
                _log(f"[weather] Open-Meteo 返回 {resp.status_code}")
                return None

            data = resp.json()
            current = data.get("current", {})
            daily = data.get("daily", {})

            weather_code = current.get("weather_code", -1)
            daily_code = daily.get("weather_code", [None])[0]

            # 当前天气描述
            weather_desc = _WMO_CODES.get(weather_code, "未知")
            # 日间天气描述（如果和当前不同则补充）
            weather_day = _WMO_CODES.get(daily_code, weather_desc)

            # 提取日出日落，截取时间部分
            sunrise_raw = (daily.get("sunrise") or [""])[0]
            sunset_raw = (daily.get("sunset") or [""])[0]
            sunrise = sunrise_raw.split("T")[1] if "T" in sunrise_raw else sunrise_raw
            sunset = sunset_raw.split("T")[1] if "T" in sunset_raw else sunset_raw

            weather = {
                "city": resolved_name,
                "weather_desc": weather_desc,
                "weather_day": weather_day,
                "high": str(daily.get("temperature_2m_max", [""])[0]),
                "low": str(daily.get("temperature_2m_min", [""])[0]),
                "feels_like": str(current.get("apparent_temperature", "")),
                "humidity": str(current.get("relative_humidity_2m", "")),
                "wind_speed_kmph": str(current.get("wind_speed_10m", "")),
                "uv_index": str(daily.get("uv_index_max", [""])[0]),
                "rain_chance": str(daily.get("precipitation_probability_max", ["0"])[0]),
                "sunrise": sunrise,
                "sunset": sunset,
            }

            _log(f"[weather] Open-Meteo: {resolved_name} {weather_desc} "
                 f"{weather['low']}~{weather['high']}°C 体感{weather['feels_like']}°C "
                 f"湿度{weather['humidity']}% 降雨{weather['rain_chance']}%")
            return weather

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            _log(f"[weather] Open-Meteo 网络异常 (尝试 {attempt}/{_retries}): {e}")
            last_err = str(e)
            if attempt < _retries:
                _time.sleep(attempt * 2)
                continue

        except Exception as e:
            _log(f"[weather] Open-Meteo 获取失败: {e}")
            return None

    _log(f"[weather] Open-Meteo {_retries} 次重试均失败: {last_err}")
    return None


# ============ Skill Handler ============

def query(params, state, ctx):
    """
    weather.query — 查询天气并返回格式化结果。
    params: city? (str) — 查询城市，默认用配置中的城市
    """
    city = params.get("city") or None
    weather = fetch_weather(city)

    if not weather:
        return {
            "success": False,
            "reply": "😥 天气数据暂时获取不到，可能是网络问题，稍后再试试~"
        }

    # 格式化天气信息
    reply_parts = [f"🌤️ **{weather['city']}** 今日天气"]

    if weather.get("weather_day"):
        reply_parts.append(f"天气：{weather['weather_day']}")

    temp_str = ""
    if weather.get("low") and weather.get("high"):
        temp_str = f"{weather['low']}~{weather['high']}°C"
    if weather.get("feels_like"):
        temp_str += f"（体感 {weather['feels_like']}°C）"
    if temp_str:
        reply_parts.append(f"🌡️ 温度：{temp_str}")

    if weather.get("humidity"):
        reply_parts.append(f"💧 湿度：{weather['humidity']}%")

    if weather.get("wind_speed_kmph"):
        reply_parts.append(f"🌬️ 风速：{weather['wind_speed_kmph']} km/h")

    if weather.get("uv_index"):
        reply_parts.append(f"☀️ 紫外线指数：{weather['uv_index']}")

    if weather.get("rain_chance") and weather["rain_chance"] != "0":
        reply_parts.append(f"🌧️ 降雨概率：{weather['rain_chance']}%")

    if weather.get("sunrise") and weather.get("sunset"):
        reply_parts.append(f"🌅 日出/日落：{weather['sunrise']} / {weather['sunset']}")

    return {
        "success": True,
        "reply": "\n".join(reply_parts),
        "weather_data": weather,
    }


# ============ Skill 热加载注册表 ============
SKILL_REGISTRY = {
    "weather.query": query,
}
