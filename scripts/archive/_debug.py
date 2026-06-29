import pathlib
file_path = pathlib.Path(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\risk_assessment_service.py")
lines = file_path.read_text(encoding="utf-8-sig").splitlines()
for i in range(19, 25):
    print(f"L{i+1}: {repr(lines[i])}")
