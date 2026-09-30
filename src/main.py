from __future__ import annotations
import os, json, math, time, hashlib, random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError, GarminConnectTooManyRequestsError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
load_dotenv(ROOT / ".env")

NOTION_VERSION = os.getenv("NOTION_VERSION", "2022-06-28")
HEADERS = {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}
DB_FILE = DATA / "notion_databases.json"

def notion(method, path, payload=None):
    r = requests.request(method, "https://api.notion.com/v1" + path, headers=HEADERS, json=payload, timeout=60)
    if not r.ok: raise RuntimeError(f"Notion {method} {path}: {r.status_code} {r.text[:500]}")
    return r.json()

def title(text): return {"title": [{"text": {"content": str(text)[:2000]}}]}
def rich(text): return {"rich_text": [{"text": {"content": str(text)[:2000]}}]}
def num(x): return {"number": None if x is None else float(x)}
def checkbox(x): return {"checkbox": bool(x)}
def select(x): return {"select": {"name": str(x)[:100]} if x is not None else None}
def date_prop(x): return {"date": {"start": str(x)[:30]} if x else None}

def ensure_existing_schema(db_ids):
    additions={
        "activities": {"Activity Type":{"select":{"options":[{"name":"running","color":"green"},{"name":"treadmill","color":"blue"},{"name":"other","color":"gray"}]}}},
        "analysis": {
            "Activity Type":{"select":{"options":[{"name":"running","color":"green"},{"name":"treadmill","color":"blue"},{"name":"other","color":"gray"}]}},
            "Pace Range %":{"number":{"format":"number"}},
            "MRS %":{"number":{"format":"number"}},
            "HR Decoupling %":{"number":{"format":"number"}},
            "Garmin RPE":{"number":{"format":"number"}},
            "Training Load":{"number":{"format":"number"}},
            "7d Load":{"number":{"format":"number"}},
            "28d Load":{"number":{"format":"number"}},
        },
        "weekly": {
            "Week Key":{"rich_text":{}}, "Week Start":{"date":{}}, "Week End":{"date":{}},
            "Training Sessions":{"number":{"format":"number"}}, "Training Frequency CV":{"number":{"format":"number"}},
            "Training Frequency Class":{"select":{"options":[{"name":"高度規律","color":"green"},{"name":"中度規律","color":"yellow"},{"name":"波動較大","color":"red"}]}},
            "Distance km":{"number":{"format":"number"}}, "Duration min":{"number":{"format":"number"}},
            "Training Load":{"number":{"format":"number"}}, "sRPE Load":{"number":{"format":"number"}},
            "Avg HR":{"number":{"format":"number"}}, "Avg Pace min/km":{"number":{"format":"number"}},
            "HR Efficiency Slope":{"number":{"format":"number"}},
            "HR Efficiency Trend":{"select":{"options":[{"name":"持續進步","color":"green"},{"name":"持平","color":"yellow"},{"name":"下滑","color":"red"}]}},
            "Recovery Burden Ratio":{"number":{"format":"number"}}, "Recovery Burden Change":{"number":{"format":"number"}},
            "Recovery Resilience Trend":{"select":{"options":[{"name":"恢復韌性提升","color":"green"},{"name":"持平","color":"yellow"},{"name":"恢復韌性下降","color":"red"}]}},
            "MRS Avg %":{"number":{"format":"number"}}, "HR Drift Avg %":{"number":{"format":"number"}}, "HR Decoupling Avg %":{"number":{"format":"number"}},
            "Temperature Avg C":{"number":{"format":"number"}}, "Notes":{"rich_text":{}}
        },
    }
    for key, wanted in additions.items():
        if key not in db_ids:
            continue
        current=notion("GET", f"/databases/{db_ids[key]}")
        existing=current.get("properties", {})
        patch={name:schema for name,schema in wanted.items() if name not in existing}
        current_type=existing.get("Activity Type", {}).get("select")
        if current_type is not None and "Activity Type" in wanted:
            options=list(current_type.get("options", []))
            names={str(option.get("name")) for option in options}
            if "treadmill" not in names:
                patch["Activity Type"]={"select":{"options":options+[{"name":"treadmill","color":"blue"}]}}
        if patch:
            notion("PATCH", f"/databases/{db_ids[key]}", {"properties":patch})
            print(f"Notion schema 已補欄位：{key} -> {', '.join(patch)}", flush=True)

def ensure_databases():
    env_ids = {
        "activities": os.getenv("NOTION_RAW_ACTIVITIES_DB_ID"),
        "laps": os.getenv("NOTION_RAW_LAPS_DB_ID"),
        "samples": os.getenv("NOTION_RAW_DETAIL_DB_ID"),
        "analysis": os.getenv("NOTION_ANALYSIS_DB_ID"),
    }
    weekly_id=os.getenv("NOTION_WEEKLY_DB_ID")
    if weekly_id: env_ids["weekly"]=weekly_id
    if any(env_ids.values()):
        base_keys=("activities","laps","samples","analysis")
        if not all(env_ids.get(k) for k in base_keys):
            raise RuntimeError("請提供全部四個 Notion database ID：NOTION_RAW_ACTIVITIES_DB_ID、NOTION_RAW_LAPS_DB_ID、NOTION_RAW_DETAIL_DB_ID、NOTION_ANALYSIS_DB_ID")
        result = {k: v.replace("-", "") for k, v in env_ids.items()}
        DB_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        ensure_existing_schema(result)
        return result
    if DB_FILE.exists():
        stored=json.loads(DB_FILE.read_text(encoding="utf-8"))
        ensure_existing_schema(stored)
        return stored
    if not os.getenv("NOTION_PARENT_PAGE_ID"):
        raise RuntimeError("請在 .env 提供四個 database ID；若要讓程式自動建立資料庫，才需要提供 NOTION_PARENT_PAGE_ID")
    parent = os.environ["NOTION_PARENT_PAGE_ID"].replace("-", "")
    specs = {
      "activities": ("Garmin Raw Activities", {"Activity ID":{"rich_text":{}},"Start Date":{"date":{}},"Activity Type":{"select":{"options":[{"name":"running","color":"green"},{"name":"treadmill","color":"blue"},{"name":"other","color":"gray"}]}},"Distance km":{"number":{"format":"number"}},"Duration min":{"number":{"format":"number"}},"Avg HR":{"number":{"format":"number"}},"Avg Pace min/km":{"number":{"format":"number"}},"Raw Synced":{"checkbox":{}},"Raw JSON Hash":{"rich_text":{}}}),
      "laps": ("Garmin Raw Laps", {"Activity ID":{"rich_text":{}},"Lap Index":{"number":{"format":"number"}},"Lap Date":{"date":{}},"Distance m":{"number":{"format":"number"}},"Duration sec":{"number":{"format":"number"}},"Avg Speed m/s":{"number":{"format":"number"}},"Avg HR":{"number":{"format":"number"}},"Cadence":{"number":{"format":"number"}},"Power W":{"number":{"format":"number"}},"Ground Contact ms":{"number":{"format":"number"}},"Stride m":{"number":{"format":"number"}},"Vertical Osc cm":{"number":{"format":"number"}},"Raw JSON":{"rich_text":{}}}),
      "samples": ("Garmin Raw Detail JSON", {"Activity ID":{"rich_text":{}},"Start Date":{"date":{}},"Measurement Count":{"number":{"format":"number"}},"Metrics Count":{"number":{"format":"number"}},"Raw JSON Hash":{"rich_text":{}}}),
      "analysis": ("Garmin Running Analysis", {"Activity ID":{"rich_text":{}},"Date":{"date":{}},"Activity Type":{"select":{"options":[{"name":"running","color":"green"},{"name":"treadmill","color":"blue"},{"name":"other","color":"gray"}]}},"Duration min":{"number":{"format":"number"}},"Distance km":{"number":{"format":"number"}},"Pace min/km":{"number":{"format":"number"}},"Pace CV %":{"number":{"format":"number"}},"Pace Range %":{"number":{"format":"number"}},"Half Split Diff %":{"number":{"format":"number"}},"MRS %":{"number":{"format":"number"}},"Avg HR":{"number":{"format":"number"}},"HR Drift %":{"number":{"format":"number"}},"HR Decoupling %":{"number":{"format":"number"}},"TRIMP":{"number":{"format":"number"}},"sRPE Load":{"number":{"format":"number"}},"7d Load":{"number":{"format":"number"}},"28d Load":{"number":{"format":"number"}},"Cadence Change %":{"number":{"format":"number"}},"GCT Change %":{"number":{"format":"number"}},"Power W/kg":{"number":{"format":"number"}},"Temperature C":{"number":{"format":"number"}},"Training Load":{"number":{"format":"number"}},"Body Battery Diff":{"number":{"format":"number"}},"Notes":{"rich_text":{}}}),
      "weekly": ("Garmin Weekly Running Analysis", {"Week Key":{"rich_text":{}},"Week Start":{"date":{}},"Week End":{"date":{}},"Training Sessions":{"number":{"format":"number"}},"Training Frequency CV":{"number":{"format":"number"}},"Training Frequency Class":{"select":{"options":[{"name":"高度規律","color":"green"},{"name":"中度規律","color":"yellow"},{"name":"波動較大","color":"red"}]}},"Distance km":{"number":{"format":"number"}},"Duration min":{"number":{"format":"number"}},"Training Load":{"number":{"format":"number"}},"sRPE Load":{"number":{"format":"number"}},"Avg HR":{"number":{"format":"number"}},"Avg Pace min/km":{"number":{"format":"number"}},"HR Efficiency Slope":{"number":{"format":"number"}},"HR Efficiency Trend":{"select":{"options":[{"name":"持續進步","color":"green"},{"name":"持平","color":"yellow"},{"name":"下滑","color":"red"}]}},"Recovery Burden Ratio":{"number":{"format":"number"}},"Recovery Burden Change":{"number":{"format":"number"}},"Recovery Resilience Trend":{"select":{"options":[{"name":"恢復韌性提升","color":"green"},{"name":"持平","color":"yellow"},{"name":"恢復韌性下降","color":"red"}]}},"MRS Avg %":{"number":{"format":"number"}},"HR Drift Avg %":{"number":{"format":"number"}},"HR Decoupling Avg %":{"number":{"format":"number"}},"Temperature Avg C":{"number":{"format":"number"}},"Notes":{"rich_text":{}}})
    }
    result = {}
    for key, (name, props) in specs.items():
        db = notion("POST", "/databases", {"parent":{"type":"page_id","page_id":parent},"title":[{"type":"text","text":{"content":name}}],"properties":{"Name":{"title":{}}, **props}})
        result[key] = db["id"]
        time.sleep(.4)
    DB_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

def find_page(db, prop, value):
    q = notion("POST", f"/databases/{db}/query", {"filter":{"property":prop,"rich_text":{"equals":str(value)}}})
    results = q.get("results") or []
    return results[0] if results else None

def ppage(db, props, children=None, unique_prop=None, unique_value=None):
    props = dict(props)
    name = props.pop("Name", "record")
    notion_props = {"Name": title(name), **props}
    existing = find_page(db, unique_prop, unique_value) if unique_prop and unique_value is not None else None
    if existing:
        return notion("PATCH", f"/pages/{existing['id']}", {"properties": notion_props})
    body={"parent":{"database_id":db},"properties":notion_props}
    if children: body["children"] = children
    return notion("POST", "/pages", body)

def blocks_for_json(obj):
    text=json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return [{"object":"block","type":"code","code":{"rich_text":[{"type":"text","text":{"content":text[i:i+1200]}}],"language":"json"}} for i in range(0,len(text),1200)]

def upsert_raw_detail(db, props, raw_obj):
    aid = next((v["rich_text"][0]["text"]["content"] for k,v in props.items() if k == "Activity ID" and v.get("rich_text")), None)
    existing = find_page(db, "Activity ID", aid) if aid else None
    if existing:
        return ppage(db, props, unique_prop="Activity ID", unique_value=aid)
    page = ppage(db, props)
    page_id = page["id"]
    blocks = blocks_for_json(raw_obj)
    for i in range(0, len(blocks), 25):
        notion("PATCH", f"/blocks/{page_id}/children", {"children": blocks[i:i+25]})
        time.sleep(.2)
    return page

def getv(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None: return d[k]
    return default

def safe_float(x):
    try: return float(x) if x is not None else None
    except: return None

def pace(speed): return 1000/(speed*60) if speed and speed>0 else None

def garmin_pause():
    low = int(os.getenv("GARMIN_JITTER_MIN_SECONDS", "30"))
    high = int(os.getenv("GARMIN_JITTER_MAX_SECONDS", "45"))
    if high < low: low, high = high, low
    time.sleep(random.randint(low, high))

def _d1_config():
    return {
        "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        "api_token": os.getenv("CLOUDFLARE_API_TOKEN"),
        "database_id": os.getenv("CLOUDFLARE_D1_DATABASE_ID"),
    }


def execute_d1_query(sql: str, params: list | None = None) -> dict | None:
    """
    透過Cloudflare D1的HTTP API執行SQL。跟 garmin-to-Notion-New 共用同一個D1資料庫，
    這樣兩個repo才能共用同一份Garmin token，不用手動同步。
    D1寫入/讀取失敗都只印警告、回傳None，不會讓主流程中斷。
    """
    config = _d1_config()
    account_id, api_token, database_id = config["account_id"], config["api_token"], config["database_id"]

    if not all([account_id, api_token, database_id]):
        print("Warning: Cloudflare D1 環境變數未設定齊全，跳過D1操作。")
        return None

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    body = {"sql": sql, "params": params or []}

    try:
        response = requests.post(url, headers=headers, json=body, timeout=15)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            print(f"Warning: D1操作失敗: {result}")
            return None
        return result
    except Exception as e:
        print(f"Warning: D1操作時發生例外: {e}")
        return None


def get_token_from_d1() -> str | None:
    try:
        sql = "SELECT value FROM credentials WHERE key = ?"
        result = execute_d1_query(sql, ["garmin_auth_token"])
        if not result:
            return None
        rows = (result.get('result') or [{}])[0].get('results', [])
        if rows and rows[0].get('value'):
            return rows[0]['value']
        return None
    except Exception as e:
        print(f"Warning: 無法從D1讀取Garmin token: {e}")
        return None


def write_token_to_d1(garmin_client) -> None:
    try:
        token_str = garmin_client.client.dumps()
        sql = """
            INSERT OR REPLACE INTO credentials (key, value, updated_at)
            VALUES (?, ?, ?)
        """
        params = ["garmin_auth_token", token_str, datetime.now(ZoneInfo("UTC")).isoformat()]
        result = execute_d1_query(sql, params)
        if result:
            print("已將更新後的Garmin token寫回D1。")
    except Exception as e:
        print(f"Warning: 無法將更新後的Garmin token寫回D1: {e}")


def seed_tokenstore_from_env(tokenstore):
    """
    寫入本地tokenstore用的token內容，優先來源是D1(跟garmin-to-Notion-New共用)，
    D1讀不到才退回用 GARMIN_AUTH_TOKEN 這個環境變數(原本叫GARMIN_TOKEN_JSON，已改名跟另一個repo統一)。
    """
    token_json = get_token_from_d1()
    if token_json:
        print("使用D1裡的最新Garmin token。")
    else:
        token_json = os.getenv("GARMIN_AUTH_TOKEN", "").strip()
        if token_json:
            print("D1沒有資料或無法連線，改用 GARMIN_AUTH_TOKEN 環境變數當作起始值。")

    if not token_json:
        return
    try:
        parsed = json.loads(token_json)
        if not isinstance(parsed, dict):
            raise ValueError("token JSON 必須是 object")
    except json.JSONDecodeError as exc:
        raise RuntimeError("GARMIN_AUTH_TOKEN 不是有效 JSON；請使用單行壓縮 JSON，並確認 .env 沒有未跳脫的換行") from exc
    token_dir = Path(tokenstore)
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file = token_dir / "garmin_tokens.json"
    token_file.write_text(json.dumps(parsed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass
    print(f"已將 GARMIN_AUTH_TOKEN 寫入本地 tokenstore：{token_file}")

def init_garmin():
    tokenstore_value = os.getenv("GARMINTOKENS", "~/.garminconnect")
    tokenstore = os.path.expanduser(os.path.expandvars(tokenstore_value))
    seed_tokenstore_from_env(tokenstore)
    try:
        g = Garmin()
        g.login(tokenstore)
        print(f"Garmin 已使用本地 token 登入：{tokenstore}")
        write_token_to_d1(g)
        return g
    except GarminConnectTooManyRequestsError as exc:
        raise RuntimeError("Garmin token 恢復或登入被 HTTP 429 限流。請停止重試，等待數小時至 24 小時後再試。") from exc
    except (GarminConnectAuthenticationError, GarminConnectConnectionError):
        print("本地 Garmin token 無效或不存在，改用帳號密碼進行一次完整登入。")
    except Exception as exc:
        if "429" in str(exc) or "rate limited" in str(exc).lower():
            raise RuntimeError("Garmin 目前對此 IP 暫時限流（HTTP 429）。請停止重試，等待數小時至 24 小時後再試。") from exc
        print(f"本地 token 載入失敗，改用帳號密碼登入：{exc}")
    try:
        email = os.environ["GARMIN_EMAIL"]; password = os.environ["GARMIN_PASSWORD"]
        g = Garmin(email=email, password=password)
        g.login(tokenstore)
        print(f"Garmin 完整登入成功，token 已保存至：{tokenstore}")
        write_token_to_d1(g)
        return g
    except Exception as exc:
        if "429" in str(exc) or "TooManyRequests" in str(exc) or "rate limited" in str(exc).lower():
            raise RuntimeError("Garmin 完整登入被 HTTP 429 限流。請停止重試，等待數小時至 24 小時後再試；恢復後只需成功登入一次，後續會使用本地 token。") from exc
        raise RuntimeError(f"Garmin 登入失敗：{exc}") from exc

def fetch_garmin(start, end):
    g=init_garmin()
    print(f"正在向 Garmin 查詢活動：{start.isoformat()} 到 {end.isoformat()} ...", flush=True)
    try:
        acts=g.get_activities_by_date(start.isoformat(), end.isoformat()) or []
        print(f"Garmin 活動查詢完成，共取得 {len(acts)} 筆，正在篩選跑步活動...", flush=True)
    except Exception as exc:
        if "429" in str(exc) or "rate limited" in str(exc).lower():
            raise RuntimeError("Garmin 活動查詢被 HTTP 429 限流。請停止重試並稍後再執行。") from exc
        raise
    def is_run(a):
        activity_type = getv(a, "activityType", default={})
        type_key = activity_type.get("typeKey", "") if isinstance(activity_type, dict) else str(activity_type)
        return "run" in type_key.lower()
    return g, [a for a in acts if is_run(a)]

def activity_category(activity):
    activity_type=activity.get("activityType", {}) if isinstance(activity, dict) else {}
    event_type=activity.get("eventType", {}) if isinstance(activity, dict) else {}
    parts=[activity.get("activityName", "") if isinstance(activity, dict) else ""]
    for value in (activity_type, event_type):
        if isinstance(value, dict): parts.extend(str(v) for v in value.values())
        else: parts.append(str(value))
    text=" ".join(parts).lower()
    if any(token in text for token in ("treadmill", "indoor", "跑步機", "跑步机")):
        return "treadmill"
    if any(token in text for token in ("run", "running", "跑步")):
        return "running"
    return "other"

def recursive_values(obj, key_terms):
    values=[]
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = str(key).lower()
            if any(term in key_lower for term in key_terms):
                number = safe_float(value)
                if number is not None: values.append(number)
            values.extend(recursive_values(value, key_terms))
    elif isinstance(obj, list):
        for value in obj: values.extend(recursive_values(value, key_terms))
    return values

def first_recursive_value(objects, key_names):
    wanted={str(name).lower() for name in key_names}
    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if str(key).lower() in wanted:
                    number=safe_float(value)
                    if number is not None: return number
                found=walk(value)
                if found is not None: return found
        elif isinstance(obj, list):
            for value in obj:
                found=walk(value)
                if found is not None: return found
        return None
    for obj in objects:
        found=walk(obj)
        if found is not None: return found
    return None

def stream_average(details, key_terms):
    descriptors = details.get("metricDescriptors", []) if isinstance(details, dict) else []
    rows = details.get("activityDetailMetrics", []) if isinstance(details, dict) else []
    indices=[]
    for i, descriptor in enumerate(descriptors):
        key = str(descriptor.get("key", "")).lower() if isinstance(descriptor, dict) else ""
        if any(term in key for term in key_terms): indices.append(i)
    values=[]
    for row in rows:
        metrics = row.get("metrics", []) if isinstance(row, dict) else []
        for i in indices:
            if i < len(metrics):
                number=safe_float(metrics[i])
                if number is not None: values.append(number)
    return sum(values)/len(values) if values else None

def analyse(a, laps, details=None):
    details = details if isinstance(details, dict) else {}
    summary = details.get("summaryDTO", {}) if isinstance(details.get("summaryDTO", {}), dict) else {}
    dist=safe_float(getv(a,"distance",default=summary.get("distance",0))) or 0
    dur=safe_float(getv(a,"duration",default=summary.get("duration",0))) or 0
    speed=safe_float(getv(a,"averageSpeed",default=summary.get("averageSpeed")))
    avg_hr=safe_float(getv(a,"averageHR",default=summary.get("averageHR")))
    load=safe_float(getv(a,"activityTrainingLoad",default=summary.get("activityTrainingLoad")))
    ls=pd.DataFrame(laps)
    def col(*names):
        for n in names:
            if n in ls: return pd.to_numeric(ls[n],errors="coerce")
        return pd.Series(dtype=float)
    lap_speed=col("averageSpeed","avgSpeed")
    lap_hr=col("averageHR","avgHR")
    valid=pd.DataFrame({"speed":lap_speed,"hr":lap_hr}).dropna()
    p=lap_speed.map(pace).dropna()
    hr=lap_hr.dropna(); cad=col("averageRunCadence","cadence").dropna(); gct=col("groundContactTime","groundContact").dropna()
    half=max(1,len(valid)//2)
    first=p.iloc[:half].mean() if len(p) else None; second=p.iloc[half:].mean() if len(p)>half else None
    first_hr=valid["hr"].iloc[:half].mean() if len(valid) else None; second_hr=valid["hr"].iloc[half:].mean() if len(valid)>half else None
    first_speed=valid["speed"].iloc[:half].mean() if len(valid) else None
    second_speed=valid["speed"].iloc[half:].mean() if len(valid)>half else None
    first_eff=(first_speed/first_hr if first_speed is not None and first_hr else None)
    second_eff=(second_speed/second_hr if second_speed is not None and second_hr else None)
    duration_min=dur/60
    max_hr=safe_float(os.getenv("MAX_HR")); rest_hr=safe_float(os.getenv("REST_HR"))
    hr_reserve=((avg_hr-rest_hr)/(max_hr-rest_hr)) if max_hr and rest_hr and avg_hr and max_hr>rest_hr else None
    trimp=(duration_min*hr_reserve*math.exp(1.92*hr_reserve) if hr_reserve is not None and 0 <= hr_reserve <= 1 else None)
    aid=str(getv(a,"activityId",default=""))
    rpe_raw=first_recursive_value((a, details, summary), ("directWorkoutRpe", "workoutRpe", "perceivedEffort", "perceivedExertion"))
    # Garmin 常見格式為 0–100 的整數，例如 30 代表 RPE 3；也兼容已是 0–10 的格式。
    srpe=(rpe_raw/10.0 if rpe_raw is not None and rpe_raw > 10 else rpe_raw)
    srpe_load=(srpe*duration_min if srpe is not None and 0 <= srpe <= 10 else None)
    weight=safe_float(os.getenv("WEIGHT_KG"))
    avg_power=safe_float(getv(a,"averagePower",default=summary.get("averagePower")))
    if avg_power is None: avg_power=stream_average(details, ("directpower", "power"))
    temperature=first_recursive_value((a, details, summary), ("averageTemperature", "temperature", "avgTemperature", "airTemperature"))
    if temperature is None:
        temperature=stream_average(details, ("directairtemperature", "directtemperature", "temperature", "temp"))
    if temperature is None:
        values=recursive_values(details, ("averagetemperature", "directtemperature"))
        temperature=sum(values)/len(values) if values else None
    pace_range=((p.max()-p.min())/p.mean()*100 if len(p)>1 and p.mean() else None)
    mrs=((second-first)/first*100 if first and second else None)
    hr_decoupling=((first_eff-second_eff)/first_eff*100 if first_eff and second_eff else None)
    notes=[]
    if trimp is None: notes.append("TRIMP需設定MAX_HR與REST_HR")
    if srpe_load is None: notes.append("Garmin detail未提供summaryDTO.directWorkoutRpe；請確認手錶Self Evaluation設定與活動是否完成同步")
    if weight is None or avg_power is None: notes.append("Power W/kg需功率資料與WEIGHT_KG")
    if temperature is None: notes.append("detail中未找到溫度資料")
    return {"Name":str(getv(a,"activityName",default="Garmin Analysis")),"Activity ID":aid,"Date":str(getv(a,"startTimeLocal",default=summary.get("startTimeLocal","")))[:10],"Activity Type":activity_category(a),"Duration min":duration_min,"Distance km":dist/1000,"Pace min/km":pace(speed),"Pace CV %":(p.std()/p.mean()*100 if len(p)>1 and p.mean() else None),"Pace Range %":pace_range,"Half Split Diff %":mrs,"MRS %":mrs,"Avg HR":avg_hr,"HR Drift %":((second_hr-first_hr)/first_hr*100 if first_hr and second_hr else None),"HR Decoupling %":hr_decoupling,"Garmin RPE":rpe_raw,"TRIMP":trimp,"sRPE Load":srpe_load,"7d Load":None,"28d Load":None,"Cadence Change %":((cad.iloc[-1]-cad.iloc[0])/cad.iloc[0]*100 if len(cad)>1 and cad.iloc[0] else None),"GCT Change %":((gct.iloc[-1]-gct.iloc[0])/gct.iloc[0]*100 if len(gct)>1 and gct.iloc[0] else None),"Power W/kg":(avg_power/weight if avg_power is not None and weight else None),"Temperature C":temperature,"Training Load":load,"Body Battery Diff":safe_float(getv(a,"differenceBodyBattery",default=summary.get("differenceBodyBattery"))),"Notes":"；".join(notes) or "四個補充欄位均已成功計算或擷取"}

def notion_value(prop):
    if not isinstance(prop, dict): return None
    typ=prop.get("type")
    if typ == "number": return prop.get("number")
    if typ == "date":
        d=prop.get("date") or {}
        return d.get("start")
    if typ == "select":
        s=prop.get("select") or {}
        return s.get("name")
    if typ == "title":
        arr=prop.get("title") or []
        return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in arr)
    if typ == "rich_text":
        arr=prop.get("rich_text") or []
        return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in arr)
    return None

def all_notion_rows(db):
    rows=[]; cursor=None
    while True:
        payload={"page_size":100}
        if cursor: payload["start_cursor"]=cursor
        q=notion("POST", f"/databases/{db}/query", payload)
        rows.extend(q.get("results", []))
        if not q.get("has_more"): break
        cursor=q.get("next_cursor")
        if not cursor: break
    return rows

def weekly_value(row, key):
    return notion_value((row.get("properties") or {}).get(key, {}))

def classify_frequency(cv):
    if cv is None: return None
    if cv < 0.3: return "高度規律"
    if cv < 0.6: return "中度規律"
    return "波動較大"

def classify_efficiency(slope):
    if slope is None: return None
    if slope > 0.001: return "持續進步"
    if slope < -0.001: return "下滑"
    return "持平"

def classify_recovery(change):
    if change is None: return None
    if change < -0.05: return "恢復韌性提升"
    if change > 0.05: return "恢復韌性下降"
    return "持平"

def linear_slope(values):
    clean=[float(v) for v in values if v is not None and np.isfinite(float(v))]
    if len(clean) < 2: return None
    return float(np.polyfit(np.arange(len(clean), dtype=float), np.array(clean), 1)[0])

def sync_weekly(analysis_db, weekly_db):
    rows=[]
    for page in all_notion_rows(analysis_db):
        record={k:weekly_value(page,k) for k in ("Date","Activity Type","Distance km","Duration min","Pace min/km","Avg HR","HR Drift %","HR Decoupling %","MRS %","Training Load","sRPE Load","Body Battery Diff","Temperature C")}
        try: record["Date"]=date.fromisoformat(str(record["Date"])[:10])
        except Exception: continue
        if record.get("Activity Type") not in (None, "running", "treadmill"): continue
        rows.append(record)
    if not rows:
        print("Weekly Analysis：每日 Analysis 尚無可用資料，略過。", flush=True); return
    df=pd.DataFrame(rows).sort_values("Date")
    df["week_start"]=[d-timedelta(days=d.weekday()) for d in df["Date"]]
    grouped=[]
    for ws, g in df.groupby("week_start", sort=True):
        grouped.append({
            "week_start":ws, "week_end":ws+timedelta(days=6), "sessions":len(g),
            "distance":pd.to_numeric(g["Distance km"],errors="coerce").sum(min_count=1),
            "duration":pd.to_numeric(g["Duration min"],errors="coerce").sum(min_count=1),
            "training_load":pd.to_numeric(g["Training Load"],errors="coerce").sum(min_count=1),
            "srpe_load":pd.to_numeric(g["sRPE Load"],errors="coerce").sum(min_count=1),
            "avg_hr":pd.to_numeric(g["Avg HR"],errors="coerce").mean(),
            "avg_pace":pd.to_numeric(g["Pace min/km"],errors="coerce").mean(),
            "mrs":pd.to_numeric(g["MRS %"],errors="coerce").mean(),
            "hr_drift":pd.to_numeric(g["HR Drift %"],errors="coerce").mean(),
            "hr_decoupling":pd.to_numeric(g["HR Decoupling %"],errors="coerce").mean(),
            "temperature":pd.to_numeric(g["Temperature C"],errors="coerce").mean(),
            "recovery_ratio":(pd.to_numeric(-g["Body Battery Diff"],errors="coerce").sum(min_count=1) / pd.to_numeric(g["Training Load"],errors="coerce").sum(min_count=1)) if pd.to_numeric(g["Training Load"],errors="coerce").sum(min_count=1) not in (None, 0) else None,
        })
    weekly=pd.DataFrame(grouped).sort_values("week_start").reset_index(drop=True)
    # 補入活動區間內沒有跑步的完整週，否則訓練次數 CV 會漏掉零訓練週。
    if len(weekly):
        week_index=list(pd.date_range(weekly["week_start"].min(), weekly["week_start"].max(), freq="7D").date)
        weekly=weekly.set_index("week_start").reindex(week_index).rename_axis("week_start").reset_index()
        weekly["week_end"]=[d+timedelta(days=6) for d in weekly["week_start"]]
        for col_name in ("sessions","distance","duration","training_load","srpe_load"):
            weekly[col_name]=weekly[col_name].fillna(0)
    for i, row in weekly.iterrows():
        counts=[]
        for j in range(max(0,i-3), i+1): counts.append(float(weekly.loc[j,"sessions"]))
        mean_count=float(np.mean(counts)); freq_cv=float(np.std(counts, ddof=0)/mean_count) if mean_count else None
        eff=[]
        for j in range(max(0,i-5), i+1):
            p=weekly.loc[j,"avg_pace"]; h=weekly.loc[j,"avg_hr"]
            if pd.notna(p) and pd.notna(h) and p>0 and h>0: eff.append(1000/(float(p)*60)/float(h))
        eff_slope=linear_slope(eff)
        recent=weekly.loc[max(0,i-2):i,"recovery_ratio"].dropna().tolist()
        early=weekly.loc[max(0,i-5):max(0,i-3),"recovery_ratio"].dropna().tolist() if i>=3 else []
        recent_mean=float(np.mean(recent)) if recent else None; early_mean=float(np.mean(early)) if early else None
        recovery_change=(recent_mean-early_mean) if recent_mean is not None and early_mean is not None else None
        week_key=f"{row['week_start'].isoformat()}"
        note=[]
        if len(counts)<4: note.append("訓練頻率CV目前少於4週，先視為初步值")
        if len(early)<1: note.append("恢復負擔比變化需至少4週資料")
        props={
            "Week Key":rich(week_key), "Week Start":date_prop(row["week_start"].isoformat()), "Week End":date_prop(row["week_end"].isoformat()),
            "Training Sessions":num(row["sessions"]), "Training Frequency CV":num(freq_cv), "Training Frequency Class":select(classify_frequency(freq_cv)),
            "Distance km":num(row["distance"]), "Duration min":num(row["duration"]), "Training Load":num(row["training_load"]), "sRPE Load":num(row["srpe_load"]),
            "Avg HR":num(row["avg_hr"]), "Avg Pace min/km":num(row["avg_pace"]), "HR Efficiency Slope":num(eff_slope), "HR Efficiency Trend":select(classify_efficiency(eff_slope)),
            "Recovery Burden Ratio":num(row["recovery_ratio"]), "Recovery Burden Change":num(recovery_change), "Recovery Resilience Trend":select(classify_recovery(recovery_change)),
            "MRS Avg %":num(row["mrs"]), "HR Drift Avg %":num(row["hr_drift"]), "HR Decoupling Avg %":num(row["hr_decoupling"]), "Temperature Avg C":num(row["temperature"]), "Notes":rich("；".join(note) or "週彙總資料完整")
        }
        ppage(weekly_db, {"Name":f"Week {week_key}", **props}, unique_prop="Week Key", unique_value=week_key)
    print(f"Weekly Analysis：已更新 {len(weekly)} 週資料。", flush=True)

def app_today():
    timezone_name = os.getenv("APP_TIMEZONE", "Asia/Taipei")
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except Exception as exc:
        raise ValueError(f"APP_TIMEZONE 無效：{timezone_name!r}；請使用 IANA 時區，例如 Asia/Taipei") from exc

def run():
    start_text = (os.getenv("START_DATE") or "").strip()
    end_text = (os.getenv("END_DATE") or "").strip()
    today = app_today()
    try:
        if not start_text or start_text.lower() == "auto":
            days_back = int(os.getenv("SYNC_DAYS_BACK", "2"))
            if days_back < 0: raise ValueError("SYNC_DAYS_BACK 不可小於 0")
            start = today - timedelta(days=days_back)
            start_text = start.isoformat()
        else:
            start = date.fromisoformat(start_text)
        if not end_text or end_text.lower() == "auto":
            end = today
            end_text = end.isoformat()
        else:
            end = date.fromisoformat(end_text)
    except ValueError as exc:
        raise ValueError(f"日期格式錯誤：START_DATE={start_text!r}, END_DATE={end_text!r}；請使用 YYYY-MM-DD，例如 2026-06-01") from exc
    if start > end:
        raise ValueError(f"日期範圍錯誤：START_DATE {start} 晚於 END_DATE {end}")
    db=ensure_databases(); g, acts=fetch_garmin(start,end)
    print(f"符合跑步條件的活動：{len(acts)} 筆。接下來每筆 detail 與 splits 請求前會等待 30–45 秒。", flush=True)
    all_analysis=[]
    for index, a in enumerate(acts, 1):
        aid=str(getv(a,"activityId")); details={}; splits=[]
        print(f"[{index}/{len(acts)}] 開始處理 Activity ID {aid} ...", flush=True)
        try:
            print(f"[{index}/{len(acts)}] 等待後取得 activity detail ...", flush=True)
            garmin_pause(); details=g.get_activity_details(int(aid)) or {}
        except Exception as e: details={"error":str(e)}
        activity_summary={}
        if first_recursive_value((a, details), ("directWorkoutRpe", "workoutRpe", "perceivedEffort", "perceivedExertion")) is None:
            try:
                print(f"[{index}/{len(acts)}] detail未找到RPE，等待後查詢活動摘要 ...", flush=True)
                garmin_pause(); activity_summary=g.get_activity(int(aid)) or {}
                details["_activitySummaryFallback"]=activity_summary
            except Exception as exc:
                print(f"[{index}/{len(acts)}] 活動摘要RPE查詢失敗：{exc}", flush=True)
        try:
            print(f"[{index}/{len(acts)}] 等待後取得 splits ...", flush=True)
            garmin_pause(); splits=(g.get_activity_splits(int(aid)) or {}).get("lapDTOs",[])
        except Exception: splits=[]
        rawhash=hashlib.sha256(json.dumps(details,sort_keys=True,default=str).encode()).hexdigest()
        dist=safe_float(getv(a,"distance",default=0)) or 0; speed=safe_float(getv(a,"averageSpeed")); st=str(getv(a,"startTimeLocal",default=""))[:10]
        ppage(db["activities"],{"Name":getv(a,"activityName",default=aid),"Activity ID":rich(aid),"Start Date":date_prop(st),"Activity Type":select(activity_category(a)),"Distance km":num(dist/1000),"Duration min":num((safe_float(getv(a,"duration",default=0)) or 0)/60),"Avg HR":num(getv(a,"averageHR")),"Avg Pace min/km":num(pace(speed)),"Raw Synced":checkbox(True),"Raw JSON Hash":rich(rawhash)}, unique_prop="Activity ID", unique_value=aid)
        for i,l in enumerate(splits,1):
            ppage(db["laps"],{"Name":f"{aid}-lap-{i}","Activity ID":rich(aid),"Lap Index":num(i),"Lap Date":date_prop(st),"Distance m":num(getv(l,"distance")),"Duration sec":num(getv(l,"duration")),"Avg Speed m/s":num(getv(l,"averageSpeed")),"Avg HR":num(getv(l,"averageHR")),"Cadence":num(getv(l,"averageRunCadence")),"Power W":num(getv(l,"averagePower")),"Ground Contact ms":num(getv(l,"groundContactTime")),"Stride m":num(getv(l,"strideLength")),"Vertical Osc cm":num(getv(l,"verticalOscillation")),"Raw JSON":rich(json.dumps(l,ensure_ascii=False,default=str))}, unique_prop="Name", unique_value=f"{aid}-lap-{i}")
        raw_bundle={"activity":a,"details":details,"splits":splits}
        sample_props={"Name":f"{aid}-detail", "Activity ID":rich(aid),"Start Date":date_prop(st),"Measurement Count":num(details.get("measurementCount")),"Metrics Count":num(details.get("metricsCount")),"Raw JSON Hash":rich(rawhash)}
        if os.getenv("STORE_DETAIL_JSON_BLOCKS","true").lower()=="true":
            upsert_raw_detail(db["samples"], sample_props, raw_bundle)
        else:
            ppage(db["samples"], sample_props, unique_prop="Activity ID", unique_value=aid)
        result=analyse(a,splits,details); all_analysis.append(result)
        print(f"[{index}/{len(acts)}] 欄位診斷：Garmin RPE={'有' if result.get('Garmin RPE') is not None else '無'}；Temperature C={'有' if result.get('Temperature C') is not None else '無'}；Power W/kg={'有' if result.get('Power W/kg') is not None else '無'}。", flush=True)
        print(f"[{index}/{len(acts)}] Activity ID {aid} 已完成並寫入 raw data。", flush=True)
        time.sleep(.5)
    # 在全部活動完成後計算跨日滾動負荷，再回寫分析資料庫。
    dates=pd.to_datetime([r["Date"] for r in all_analysis], errors="coerce")
    loads=pd.Series([r.get("Training Load") or 0 for r in all_analysis], index=dates).sort_index()
    for result in all_analysis:
        d=pd.Timestamp(result["Date"])
        result["7d Load"]=float(loads.loc[(loads.index>=d-pd.Timedelta(days=6))&(loads.index<=d)].sum())
        result["28d Load"]=float(loads.loc[(loads.index>=d-pd.Timedelta(days=27))&(loads.index<=d)].sum())
        aid=result["Activity ID"]
        props={k:(date_prop(v) if k=="Date" else rich(v) if k in ("Activity ID","Notes") else select(v) if k=="Activity Type" else num(v)) for k,v in result.items() if k!="Name"}
        ppage(db["analysis"],{"Name":f"{aid}-analysis", **props}, unique_prop="Activity ID", unique_value=aid)
    if db.get("weekly"):
        sync_weekly(db["analysis"], db["weekly"])
    else:
        print("未設定 NOTION_WEEKLY_DB_ID，略過每週彙總。", flush=True)
    print(f"完成：{len(acts)} 筆跑步活動，日期 {start} 至 {end}；原始資料已先寫入 Notion，再寫入分析結果。")

if __name__=="__main__": run()
