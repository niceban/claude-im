#!/usr/bin/env python3
"""测试 controller 复用：创建 controller，发送两条消息"""
import os
import sys
import time
import threading

sys.path.insert(0, '/Users/c/claude-im/clawrelay-feishu-server')
sys.path.insert(0, '/Users/c/claw-army/kernel')

from claude_node import ClaudeController

token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
print(f"Token: {bool(token)}, len={len(token)}")

SESSION_KEY = "test-resume-session"
MODEL = "MiniMax-M2.7"
WORKING_DIR = "/Users/c/claude-im"

os.environ["ANTHROPIC_AUTH_TOKEN"] = token

ctrl = ClaudeController(
    system_prompt="你是测试bot，只回复 OK",
    skip_permissions=True,
    model=MODEL,
    cwd=WORKING_DIR,
)

print("Starting controller...")
started = ctrl.start(wait_init_timeout=30)
print(f"Started: {started}, alive: {ctrl.alive}")

if started:
    ok = ctrl._wait_for_init(30)
    print(f"Init wait: {ok}")

    if ok:
        # 第一次 send
        print("\n=== FIRST SEND ===")
        t0 = time.time()
        result1 = ctrl.send("say hi in 3 words", timeout=60)
        t1 = time.time()
        print(f"First send done in {t1-t0:.1f}s, result={result1.result_text[:100] if result1 and result1.result_text else None}")

        # 第二次 send（复用同一 controller）
        print("\n=== SECOND SEND ===")
        t2 = time.time()
        try:
            result2 = ctrl.send("continue with 3 words", timeout=60)
            t3 = time.time()
            print(f"Second send done in {t3-t2:.1f}s, result={result2.result_text[:100] if result2 and result2.result_text else None}")
        except Exception as e:
            print(f"Second send ERROR: {e}")

    else:
        print("Init failed")
        proc = ctrl._proc
        if proc:
            import subprocess
            print("Stderr:", proc.stderr.read() if proc.stderr else 'N/A')
            print("Stdout:", proc.stdout.read() if proc.stdout else 'N/A')

ctrl.stop()
print("\nDone")
