from pathlib import Path
import json
import datetime
from flask import Flask, render_template, jsonify, abort

APP_PORT = 5000
JSON_FILENAME = "timetable.json"

app = Flask(__name__, template_folder="templates")

# --- 1. JSON 파일 로드 함수 ---
def load_json(filename: str):
    try:
        script_folder = Path(__file__).resolve().parent
    except NameError:
        script_folder = Path.cwd()
    file_path = script_folder / filename

    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# 전역으로 JSON 한 번 로드
try:
    DATA = load_json(JSON_FILENAME)
except Exception as e:
    print(f"❌ CRITICAL ERROR: JSON 로드 실패: {e}")
    DATA = {"region_data": {}, "route_name": "데이터 로드 오류"}

# --- 데이터 정규화 ---
def normalize_loaded_data(data):
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
print("DEBUG: region_data keys:", list(DATA.get("region_data", {}).keys()))

# 템플릿 전역 변수로 DATA 주입
@app.context_processor
def inject_data():
    return dict(DATA=DATA)

# --- 2. 시간 계산 헬퍼 함수 ---
def calculate_next_bus(timetable_list):
    now = datetime.datetime.now()
    time_remaining_str = "오늘 운행 종료"
    next_bus_time = None

    for time_str in timetable_list:
        try:
            clean_time_str = time_str.split('역')[0].strip()
            hour, minute = map(int, clean_time_str.split(':'))
            bus_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if bus_time > now:
                minutes_remaining = int((bus_time - now).total_seconds() / 60)
                time_remaining_str = f"다음 버스까지 약 {minutes_remaining}분 남음 ({time_str} 출발)"
                next_bus_time = time_str
                break
        except Exception:
            continue
    return time_remaining_str, next_bus_time, now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")

# --- 3. 계층적 라우트 ---

# 3-1. 읍/면 선택
@app.route("/")
def select_region():
    regions = sorted(list(DATA.get("region_data", {}).keys()))
    return render_template("menu_select.html",
                           title="1단계: 읍/면 선택",
                           menu_title="탑승할 읍/면을 선택하세요.",
                           items=regions,
                           next_route="select_station")

# 3-2. 정류장 선택
@app.route("/station_select/<region_name>")
def select_station(region_name):
    region_data = DATA.get("region_data", {}).get(region_name)
    if not region_data:
        abort(404)
    stations = sorted(list(region_data.keys()))
    return render_template("menu_select.html",
                           title=f"2단계: {region_name} 정류장 선택",
                           menu_title=f"'{region_name}' 내 정류장을 선택하세요.",
                           items=stations,
                           parent_region=region_name,
                           next_route="select_route")

# 3-3. 노선 선택
@app.route("/route_select/<region_name>/<station_name>")
def select_route(region_name, station_name):
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
                           next_route="show_timetable")

# 3-4. 시간표 표시
@app.route("/timetable/<region_name>/<station_name>/<route_name>")
def show_timetable(region_name, station_name, route_name):
    region_data = DATA.get("region_data", {}).get(region_name)
    if not region_data or station_name not in region_data:
        abort(404)

    station_data = region_data[station_name]
    route_obj = station_data.get("노선", {}).get(route_name)

    if not route_obj:
        abort(404)

    # dict이면 destinations 리스트로 변환
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
                           gps_info=gps_info)

# --- 4. 앱 실행 ---
if __name__ == "__main__":
    print("▶ 로컬 웹앱 시작: http://127.0.0.1:5000/")
    app.run(host="127.0.0.1", port=APP_PORT, debug=True)
