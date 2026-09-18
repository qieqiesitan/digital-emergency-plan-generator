"""杀掉容器里跑着的 mock 供应商进程（容器里没有 pkill/ps）。"""
import os
import signal

killed = []
for pid in os.listdir("/proc"):
    if not pid.isdigit() or int(pid) == os.getpid():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="replace")
    except OSError:
        continue
    if "mock_llm_server" in cmd:
        try:
            os.kill(int(pid), signal.SIGKILL)
            killed.append(pid)
        except OSError:
            pass
print("killed:", killed or "无")
