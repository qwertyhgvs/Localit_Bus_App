from pathlib import Path
import json
import datetime
# pytz 라이브러리를 추가하고 zoneinfo 대신 사용
import pytz 
from flask import Flask, render_template, jsonify, abort, url_for
from jinja2 import TemplateNotFound
import traceback
import sys

APP_PORT = 5000
JSON_FILENAME = "timetable.json"

app = Flask(__name__, template_folder="templates")

# ----------------------------
# 안전한 JSON 폴백 데이터 (기본값)
# ----------------------------
DEFAULT_DATA = {
    "route_name": "서천군 공영버스 다중 정류장 정보 시스템 (폴백)",
    "stations": {
        "서천특화시장": {
            "region": "서천읍",
            "gps": [36.0683, 126.709],
            "routes": {
                "한산 방면": {
                    "destinations": {
                        "한산 방면": [
                            "06:40","06:50","06:50","07:30","08:10","08:40","09:10","09:50","10:30",
                            "11:10","11:50","12:30","12:50","13:10","13:50","14:30","15:10",
                            "15:50","16:30","17:10","17:50","18:30","19:10","19:50","21:00"
                        ]
                    }
                }
            }
        },
        "서천여자정보고앞": {
            "region": "서천읍",
            "gps": [36.0807, 126.701],
            "routes": {
                "기산.한산 방면": {
                    "destinations": {
                        "기산.한산 방면": [
                            "06:40","06:50","06:50","07:30","08:10","08:40","09:10","09:50","10:30",
                            "11:10","11:50","12:30","12:50","13:10","13:50","14:30","15:10",
                            "15:50","16:30","17:10","17:50","18:30","19:10","19:50","21:00"
                        ]
                    }
                }
            }
        },
        "동강중학교 앞": {
            "region": "기산면",
            "gps": [36.071846, 126.749222],
            "routes": {
                "한산 방면": {
                    "destinations": {
                        "한산 방면": [
                            "06:40","06:50","06:50","07:30","08:10","08:40","09:10","09:50","10:30",
                            "11:10","11:50","12:30","12:50","13:10","13:50","14:30","15:10",
                            "15:50","16:30","17:10","17:50","18:30","19:10","19:50","21:00"
                        ]
                    }
                }
            }
        }
    },
    "tourism": {
        "서천 9경": {
            "관아터": {"description":"조선시대 관아 터로 역사적 가치가 높습니다.","gps":[36.0679,126.7095],"best_time":"봄, 가을"},
            "금강하구철새공원": {"description":"철새 도래지로 유명합니다.","gps":[36.0134,126.5623],"best_time":"가을~겨울"}
        },
        "서천 축제": {
            "국화축제": {"description":"가을 국화 전시 및 문화행사","month":"10월","location":"서천시 일대"},
            "멸치축제": {"description":"멸치 특산물 축제","month":"6월","location":"서천항"}
        }
    },
    "default_selection": ["서천읍", "서천특화시장", "한산 방면"]
}

# --- 1. JSON 파일 로드 함수 (안전하게) ---
def load_json_safe(filename: str):
    """
    파일을 읽어 JSON으로 파싱. 비어있거나 파싱 실패 시 예외를 발생.
    """
    script_folder = Path(__file__).resolve().parent
    file_path = script_folder / filename

    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    raw = file_path.read_text(encoding="utf-8")
    if not raw.strip():
        raise ValueError("파일이 비어 있습니다.")
    return json.loads(raw)

# 전역으로 JSON 한 번 로드 (안전 폴백 포함)
try:
    DATA = load_json_safe(JSON_FILENAME)
    print("✅ JSON 파일 로드 성공:", JSON_FILENAME)
except Exception as e:
    print("❌ CRITICAL ERROR: JSON 로드 실패:", e, file=sys.stderr)
    traceback.print_exc()
    print("▷ DEFAULT_DATA (폴백)을 사용합니다. 실제 timetable.json 파일을 확인하세요.", file=sys.stderr)
    DATA = DEFAULT_DATA.copy()

# --- 데이터 정규화 함수 ---
def normalize_loaded_data(data):
    """
    - 지원하는 구조:
      1) {"region_data": {...}}
      2) {"stations": {...}}
      3) tourism 필드가 있으면 그대로 둠
    결과: data['region_data'] 가 항상 존재하도록 보장
    """
    if not isinstance(data, dict):
        return {"region_data": {}}

    if "region_data" in data and isinstance(data["region_data"], dict):
        return data

    stations = data.get("stations")
    if stations and isinstance(stations, dict):
        region_map = {}
        for station_name, station_obj in stations.items():
            region = station_obj.get("region", "기타")
            gps = station_obj.get("gps") or station_obj.get("gps_info") or station_obj.get("gpsinfo") or []
            station_entry = {
                "gps_info": gps if isinstance(gps, list) else [],
                "노선": {}
            }
            routes = station_obj.get("routes") or {}
            for rname, robj in routes.items():
                if isinstance(robj, dict):
                    if "destinations" in robj and isinstance(robj["destinations"], dict):
                        station_entry["노선"][rname] = robj["destinations"]
                    else:
                        is_direct_map = all(isinstance(v, list) for v in robj.values()) if robj else False
                        if is_direct_map:
                            station_entry["노선"][rname] = robj
                        else:
                            dests = robj.get("destinations")
                            if isinstance(dests, list):
                                station_entry["노선"][rname] = { rname: dests }
                            else:
                                station_entry["노선"][rname] = {}
                elif isinstance(robj, list):
                    station_entry["노선"][rname] = { rname: robj }
                else:
                    station_entry["노선"][rname] = {}

            region_map.setdefault(region, {})[station_name] = station_entry

        data["region_data"] = region_map
        return data

    data.setdefault("region_data", {})
    return data

DATA = normalize_loaded_data(DATA)

# 디버그 로그: 로드된 키들
print("DEBUG: region_data keys:", list(DATA.get("region_data", {}).keys()))
if "tourism" in DATA:
    try:
        print("DEBUG: tourism keys:", list(DATA.get("tourism", {}).keys()))
    except Exception:
        pass

# 템플릿 전역 변수로 DATA 주입
@app.context_processor
def inject_data():
    return dict(DATA=DATA)

# --- 2. 시간 계산 헬퍼 함수 (KST-aware) ---
# 기존 zoneinfo 대신 pytz를 사용하여 Python 3.8 환경에서도 호환되도록 수정
def calculate_next_bus(timetable_list):
    # from zoneinfo import ZoneInfo  # Python 3.9+ 대신
    # KST = ZoneInfo("Asia/Seoul")
    
    # pytz를 사용하여 KST 시간대 정의
    KST = pytz.timezone("Asia/Seoul")

    # KST 시간으로 현재 시각을 가져옴
    now = datetime.datetime.now(tz=KST)
    
    parsed_entries = []
    for t in timetable_list:
        try:
            clean = str(t).split('역')[0].strip()
            h, m = map(int, clean.split(':'))
            # KST 시간대로 datetime 객체 생성
            dt = KST.localize(datetime.datetime(year=now.year, month=now.month, day=now.day,
                                     hour=h, minute=m, second=0))
            parsed_entries.append((dt, clean))
        except Exception:
            continue

    parsed_entries.sort(key=lambda x: x[0])

    for dt, orig_str in parsed_entries:
        if dt > now:
            mins = int((dt - now).total_seconds() // 60)
            display = f"다음 버스까지 약 {mins}분 남음 ({orig_str} 출발)"
            return display, orig_str, now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")

    if parsed_entries:
        # 오늘 운행이 끝났다면 내일 첫차 시간 계산
        first_dt_today, first_str = parsed_entries[0]
        tomorrow_dt = first_dt_today + datetime.timedelta(days=1)
        mins = int((tomorrow_dt - now).total_seconds() // 60)
        display = f"오늘 운행 종료 — 내일 첫차 {first_str}까지 약 {mins}분 남음"
        return display, first_str, now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")

    return "등록된 시간표가 없습니다.", None, now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")

# --- debug route to inspect loaded DATA quickly ---
@app.route("/_debug")
def debug_info():
    regions = list(DATA.get("region_data", {}).keys())
    sample = None
    if regions:
        r = regions[0]
        sample = {
            "region": r,
            "stations_count": len(DATA["region_data"].get(r, {})),
            "stations_sample": list(DATA["region_data"].get(r, {}).keys())[:10]
        }
    return jsonify({
        "route_name": DATA.get("route_name"),
        "regions": regions,
        "tourism_keys": list(DATA.get("tourism", {}).keys()) if DATA.get("tourism") else [],
        "sample_region": sample
    })

# ---------- UI: mode selection ----------
@app.route("/")
def index_choice():
    return render_template("index_choice.html")

# ---------- regions with mode ----------
@app.route("/regions/<mode>")
def regions_with_mode(mode):
    if mode not in ("transport", "tourism"):
        abort(404)
    if mode == "transport":
        items = sorted(list(DATA.get("region_data", {}).keys()))
    else:  # tourism
        items = sorted(list(DATA.get("tourism", {}).keys())) if DATA.get("tourism") else []
    return render_template("menu_select.html",
                           title="1단계: 선택",
                           menu_title=("탑승할 읍/면을 선택하세요." if mode == "transport" else "관광 카테고리를 선택하세요."),
                           items=items,
                           next_route="select_station_with_mode",
                           mode=mode)

# ---------- station / category listing ----------
@app.route("/station_select/<mode>/<region_name>")
def select_station_with_mode(mode, region_name):
    if mode not in ("transport", "tourism"):
        abort(404)
    if mode == "transport":
        region_data = DATA.get("region_data", {}).get(region_name)
        if not region_data:
            abort(404)
        items = sorted(list(region_data.keys()))
        return render_template("menu_select.html",
                               title=f"2단계: {region_name} 정류장 선택",
                               menu_title=f"'{region_name}' 내 정류장을 선택하세요.",
                               items=items,
                               parent_region=region_name,
                               next_route="select_route_with_mode",
                               mode=mode)
    else:
        category = region_name
        cat_obj = DATA.get("tourism", {}).get(category)
        if not cat_obj:
            abort(404)
        items = sorted(list(cat_obj.keys()))
        return render_template("menu_select.html",
                               title=f"2단계: {category} 목록",
                               menu_title=f"'{category}'에서 항목을 선택하세요.",
                               items=items,
                               parent_region=category,
                               next_route="tourism_detail",
                               mode=mode)

# ---------- route selection (transport only) ----------
@app.route("/route_select/<mode>/<region_name>/<station_name>")
def select_route_with_mode(mode, region_name, station_name):
    if mode != "transport":
        abort(404)
    region_data = DATA.get("region_data", {}).get(region_name)
    if not region_data or station_name not in region_data:
        abort(404)
    station_data = region_data[station_name]
    routes_obj = station_data.get("노선", {})
    routes = sorted(list(routes_obj.keys()))
    return render_template("menu_select.html",
                           title=f"3단계: {station_name} 노선 선택",
                           menu_title=f"'{station_name}'에서 가는 방면을 선택하세요.",
                           items=routes,
                           parent_region=region_name,
                           parent_station=station_name,
                           next_route="show_timetable_with_mode",
                           mode=mode)

# ---------- timetable display (transport) ----------
@app.route("/timetable/<mode>/<region_name>/<station_name>/<route_name>")
def show_timetable_with_mode(mode, region_name, station_name, route_name):
    if mode != "transport":
        abort(404)
    region_data = DATA.get("region_data", {}).get(region_name)
    if not region_data or station_name not in region_data:
        abort(404)

    station_data = region_data[station_name]
    route_obj = station_data.get("노선", {}).get(route_name)
    if not route_obj:
        abort(404)

    if isinstance(route_obj, dict):
        first_destination = next(iter(route_obj.values()))
        timetable_list = first_destination if isinstance(first_destination, list) else []
    elif isinstance(route_obj, list):
        timetable_list = route_obj
    else:
        timetable_list = []

    if not timetable_list:
        abort(404)

    gps_info = station_data.get("gps_info", [])
    time_remaining_str, next_bus_time, current_time_str = calculate_next_bus(timetable_list)

    return render_template("timetable_view.html",
                           title=f"{station_name} ({route_name}) 시간표",
                           current_time=current_time_str,
                           time_remaining=time_remaining_str,
                           route_name=route_name,
                           departure_station=station_name,
                           next_bus_time=next_bus_time,
                           timetable=timetable_list,
                           gps_info=gps_info,
                           mode=mode)

# ---------- tourism detail (category -> place) ----------
@app.route("/tourism/<mode>/<region_name>/<station_name>")
def tourism_detail(mode, region_name, station_name):
    if mode != "tourism":
        abort(404)
    category = region_name
    place = station_name
    cat_obj = DATA.get("tourism", {}).get(category)
    if not cat_obj or place not in cat_obj:
        abort(404)
    place_info = cat_obj[place]

    try:
        return render_template("tourism_view.html",
                               title=f"{place} — {category}",
                               category=category,
                               place=place,
                               info=place_info,
                               mode=mode)
    except TemplateNotFound:
        return jsonify({
            "category": category,
            "place": place,
            "info": place_info
        })

# --- 4. 앱 실행 ---
if __name__ == "__main__":
    print("▶ 로컬 웹앱 시작: http://127.0.0.1:5000/")
    # debug=True가 빠져있어 추가했습니다.
    app.run(host="127.0.0.1", port=APP_PORT, debug=True)