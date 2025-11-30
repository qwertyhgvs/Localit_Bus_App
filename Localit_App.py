from pathlib import Path
import json
import datetime
from flask import Flask, render_template, jsonify, abort

APP_PORT = 5000
JSON_FILENAME = "timetable.json"

app = Flask(__name__, template_folder="templates")

# --- 1. JSON 파일 로드 함수 (유지) ---
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
    # 데이터 로드 실패 시 앱의 최소 기능 보장
    DATA = {"region_data": {}, "route_name": "데이터 로드 오류"}

# --- 2. 시간 계산 헬퍼 함수 (로직 분리) ---
def calculate_next_bus(timetable_list):
    """주어진 시간표 리스트에서 다음 버스 시간과 남은 시간을 계산합니다."""
    now = datetime.datetime.now()
    time_remaining_str = "오늘 운행 종료"
    next_bus_time = None

    for time_str in timetable_list:
        try:
            # "13:20역" 같은 특수 문자를 제거하고 시간만 파싱
            clean_time_str = time_str.split('역')[0].strip()
            hour, minute = map(int, clean_time_str.split(':'))
            
            # 현재 날짜 기준, 시간표의 시간/분으로 대체
            bus_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if bus_time > now:
                time_difference = bus_time - now
                minutes_remaining = int(time_difference.total_seconds() / 60)
                
                time_remaining_str = f"다음 버스까지 약 {minutes_remaining}분 남음 ({time_str} 출발)"
                next_bus_time = time_str
                break
        except Exception:
            # 잘못된 포맷이면 무시하고 다음 시간으로
            continue
            
    return time_remaining_str, next_bus_time, now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")

# --- 3. 계층적 라우트 정의 (Controller) ---

# 3-1. 1단계: 읍/면 선택 (URL: /)
@app.route("/")
def select_region():
    # DATA에서 모든 읍/면 이름(키)을 가져옵니다.
    regions = sorted(list(DATA.get("region_data", {}).keys()))
    
    # regions_menu.html 템플릿에 데이터와 다음 경로를 전달합니다.
    # next_route는 엔드포인트 이름(함수명)을 넘겨줍니다: select_station
    return render_template("menu_select.html",
                           title="1단계: 읍/면 선택",
                           menu_title="탑승할 읍/면을 선택하세요.",
                           items=regions,
                           next_route="select_station")

# 3-2. 2단계: 정류장 선택 (URL: /station_select/<region_name>)
@app.route("/station_select/<region_name>")
def select_station(region_name):
    region_data = DATA.get("region_data", {}).get(region_name)
    
    if not region_data:
        abort(404) # 잘못된 읍/면 이름인 경우 404 에러 반환
        
    # 선택된 읍/면 내의 모든 정류장 이름(키)을 가져옵니다.
    stations = sorted(list(region_data.keys()))
    
    return render_template("menu_select.html",
                           title=f"2단계: {region_name} 정류장 선택",
                           menu_title=f"'{region_name}' 내 정류장을 선택하세요.",
                           items=stations,
                           parent_region=region_name,    # 상위 경로(읍/면)
                           next_route="select_route")    # 엔드포인트 이름 전달

# 3-3. 3단계: 노선(방면) 선택 (URL: /route_select/<region_name>/<station_name>)
@app.route("/route_select/<region_name>/<station_name>")
def select_route(region_name, station_name):
    region_data = DATA.get("region_data", {}).get(region_name)
    
    if not region_data or station_name not in region_data:
        abort(404)
        
    station_data = region_data[station_name]
    # 안전 체크: "노선" 키가 있나
    routes_obj = station_data.get("노선", {})
    routes = sorted(list(routes_obj.keys()))
    
    return render_template("menu_select.html",
                           title=f"3단계: {station_name} 노선 선택",
                           menu_title=f"'{station_name}'에서 가는 방면을 선택하세요.",
                           items=routes,
                           parent_region=region_name,      # 상위 읍/면
                           parent_station=station_name,   # 상위 정류장
                           next_route="show_timetable")    # 엔드포인트 이름 전달


# 3-4. 4단계: 최종 시간표 표시 (URL: /timetable/<region_name>/<station_name>/<route_name>)
@app.route("/timetable/<region_name>/<station_name>/<route_name>")
def show_timetable(region_name, station_name, route_name):
    region_data = DATA.get("region_data", {}).get(region_name)
    
    # 데이터 경로 검증
    if not region_data or station_name not in region_data:
        abort(404)
        
    station_data = region_data[station_name]
    timetable_list = station_data.get("노선", {}).get(route_name)
    gps_info = station_data.get("gps_info")
    
    if not timetable_list:
        abort(404)

    # 시간 계산 헬퍼 함수 호출
    time_remaining_str, next_bus_time, current_time_str = calculate_next_bus(timetable_list)
    
    # templates/timetable_view.html로 최종 렌더링
    return render_template("timetable_view.html",
                           title=f"{station_name} ({route_name}) 시간표",
                           current_time=current_time_str,
                           time_remaining=time_remaining_str,
                           route_name=route_name,
                           departure_station=station_name,
                           next_bus_time=next_bus_time,
                           timetable=timetable_list,
                           gps_info=gps_info)

# --- 4. 앱 실행 (로컬 환경에서만 작동하도록 정리) ---
if __name__ == "__main__":
    print("▶ 로컬 웹앱 시작: http://127.0.0.1:5000/")
    app.run(host="127.0.0.1", port=APP_PORT, debug=True)
