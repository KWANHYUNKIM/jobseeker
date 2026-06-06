"""공통 경로 설정 — 데이터/실행 위치의 단일 소스.

파일을 기능별 폴더로 나눠도 screenshots/.venv 등 데이터 위치는 catch_capture 루트에
그대로 둔다. 각 모듈은 자체적으로 `Path(__file__).resolve().parent.parent`(= catch 루트)를
계산하지만, 새 코드는 여기서 import 해 쓰는 것을 권장한다.
"""
from pathlib import Path

CATCH_DIR = Path(__file__).resolve().parent          # catch_capture/
ROOT_DIR = CATCH_DIR.parent                            # jobseeker/
SCREENSHOTS_DIR = CATCH_DIR / "screenshots"
VENV_PY = CATCH_DIR / ".venv" / "bin" / "python"
DASHBOARD_DIR = CATCH_DIR / "dashboard"
JD_VIEWER_DIR = ROOT_DIR / "jd-viewer"
REFRESH_SH = JD_VIEWER_DIR / "bin" / "refresh-data.sh"
