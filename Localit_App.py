from pathlib import Path
import json
import datetime # 시간 계산을 위해 datetime 모듈 추가
from flask import Flask, render_template, jsonify
# import sys, traceback (불필요한 모듈 제거)
# import webbrowser

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
        # Render 환경에서는 이 경로를 통해 파일을 찾습니다.
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# 전역으로 JSON 한 번 로드 (앱 시작 시)
try:
    DATA = load_json(JSON_FILENAME)
except Exception as e:
    # Render 로그에 오류를 명확히 남깁니다.
    print(f"❌ CRITICAL ERROR: JSON 로드 실패: {e}")
    DATA = {
        "route_name": "데이터 로드 오류",
        "departure_station": "데이터 로드 오류",
        "timetable": [],
        "gps_info": {}
    }

# --- 2. 메인 페이지 라우트 (시간 계산 로직 복원) ---
@app.route("/")
def index():
    
    # 2-1. 현재 시간 계산
    now = datetime.datetime.now()
    current_time_str = now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")

    # 2-2. 다음 버스 시간 계산 로직 복원
    timetable_list = DATA.get("timetable", [])
    time_remaining_str = "오늘 운행 종료"
    
    for time_str in timetable_list:
        try:
            hour, minute = map(int, time_str.split(':'))
            # 현재 날짜를 기준으로 시간표의 시간/분으로 대체
            bus_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if bus_time > now:
                time_difference = bus_time - now
                minutes_remaining = int(time_difference.total_seconds() / 60)
                
                time_remaining_str = f"다음 버스까지 약 {minutes_remaining}분 남음 ({time_str} 출발)"
                break
        except ValueError:
            continue
            
    # 2-3. templates/index.html로 렌더링하면서 데이터 전달
    return render_template("index.html",
                           current_time=current_time_str, # 계산된 현재 시간 추가
                           time_remaining=time_remaining_str, # 계산된 남은 시간 추가
                           route_name=DATA.get("route_name"),
                           departure_station=DATA.get("departure_station"),
                           timetable=timetable_list,
                           gps_info=DATA.get("gps_info", {}))

# --- 3. API 엔드포인트 (유지) ---
@app.route("/api/timetable")
def api_timetable():
    return jsonify(DATA)

# --- 4. 앱 실행 (로컬 환경에서만 작동하도록 정리) ---
if __name__ == "__main__":
    # 이 블록은 gunicorn이 아닌, 로컬에서 직접 python Localit_App.py를 실행할 때만 작동합니다.
    # ngrok 코드는 제거하고 로컬 실행만 남겨둡니다.
    print("▶ 로컬 웹앱 시작: http://127.0.0.1:5000/")
    # 로컬 테스트를 위해 debug=True로 설정합니다.
    app.run(host="127.0.0.1", port=APP_PORT, debug=True)