from pathlib import Path
import json
import sys
import traceback
from flask import Flask, render_template, jsonify
import webbrowser
import threading
from pyngrok import ngrok # ngrok 라이브러리 추가

APP_PORT = 5000
JSON_FILENAME = "timetable.json"

app = Flask(__name__, template_folder="templates")

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

# 전역으로 JSON 한 번 로드 (앱 시작 시)
try:
    DATA = load_json(JSON_FILENAME)
except Exception as e:
    print("JSON 로드 실패:", e)
    DATA = {
        "route_name": "알 수 없음",
        "departure_station": "알 수 없음",
        "timetable": [],
        "gps_info": {}
    }

@app.route("/")
def index():
    # templates/index.html로 렌더링하면서 데이터 전달
    return render_template("index.html",
                           route_name=DATA.get("route_name"),
                           departure_station=DATA.get("departure_station"),
                           timetable=DATA.get("timetable", []),
                           gps_info=DATA.get("gps_info", {}))

@app.route("/api/timetable")
def api_timetable():
    return jsonify(DATA)

def open_browser_later(url):
    # 서버가 뜰 때 브라우저 자동 오픈 (백그라운드 쓰레드)
    webbrowser.open(url)

if __name__ == "__main__":
    
    # ngrok 통합 블록
    try:
        # 기존 ngrok 터널이 있다면 종료
        ngrok.kill()
        
        # ngrok 터널 열기 (HTTP) 및 Public URL 확보
        public_url = ngrok.connect(APP_PORT).public_url
        print("▶ ngrok 터널 시작: Public URL =", public_url)
        
        # 브라우저 오픈 및 Flask 서버 실행 호스트 설정
        open_url = public_url
        run_host = "0.0.0.0" # ngrok을 사용하려면 모든 인터페이스에서 수신해야 함
    
    except Exception as e:
        # ngrok 연결 실패 시 로컬 호스트로 폴백
        print(f"ngrok 연결 실패. 로컬 호스트로 실행합니다: {e}")
        open_url = f"http://127.0.0.1:{APP_PORT}/"
        run_host = "127.0.0.1"

    print("▶ 웹앱 시작: 접속 URL =", open_url)
    
    # 자동으로 브라우저를 여는 쓰레드
    threading.Timer(1.0, open_browser_later, args=(open_url,)).start()
    
    # 디버그 모드 끄려면 debug=False
    # ngrok 사용 시 use_reloader=False를 설정하여 터널이 중복 생성되는 것을 방지합니다.
    app.run(host=run_host, port=APP_PORT, debug=True, use_reloader=False)