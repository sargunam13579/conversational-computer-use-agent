import json
import urllib.request


def run_integration_check():
    print("=== NEXUS AI ASSISTANT FULL INTEGRATION VERIFICATION ===")

    # 1. Frontend Vite Server Check
    try:
        with urllib.request.urlopen('http://127.0.0.1:5173/') as response:
            html = response.read().decode('utf-8')
            print(f"[OK] Frontend UI Server: HTTP {response.status} (Serving {len(html)} bytes)")
            assert "NEXUS" in html
    except Exception as e:
        print(f"[FAIL] Frontend UI Server: {e}")

    # 2. Backend Health
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health') as response:
            health = json.loads(response.read().decode('utf-8'))
            print(f"[OK] Backend Health: status='{health.get('status')}', version='{health.get('version')}', tools={health.get('tool_count')}, llm={health.get('llm_providers')}")
    except Exception as e:
        print(f"[FAIL] Backend Health: {e}")

    # 3. Test Normal Conversation (Gemini LLM)
    print("\n--- Test A: Normal Conversation Question ---")
    try:
        req = urllib.request.Request(
            'http://127.0.0.1:8000/api/chat',
            data=json.dumps({'message': 'What is artificial intelligence? Give a concise 1-sentence definition.'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            chat_res = json.loads(response.read().decode('utf-8'))
            print(f"[OK] General Q&A Response: {chat_res.get('response')}")
            print(f"     Model Used: {chat_res.get('model_used')}, Tools Triggered: {len(chat_res.get('tool_calls', []))}")
    except Exception as e:
        print(f"[FAIL] General Q&A: {e}")

    # 4. Test System Command Intent & Tool Routing (get_system_info)
    print("\n--- Test B: System Command Routing (System Info) ---")
    try:
        req = urllib.request.Request(
            'http://127.0.0.1:8000/api/chat',
            data=json.dumps({'message': 'Please show system information and hardware status.'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            chat_res = json.loads(response.read().decode('utf-8'))
            print(f"[OK] System Command Response: {chat_res.get('response')}")
            tool_calls = chat_res.get('tool_calls', [])
            print(f"     Tool Calls Count: {len(tool_calls)}")
            for tc in tool_calls:
                print(f"     -> Tool Name: {tc.get('name')}, Success: {tc.get('success')}")
    except Exception as e:
        print(f"[FAIL] System Command: {e}")

    # 5. Test Audio/Volume System Command
    print("\n--- Test C: System Command Routing (Audio Control) ---")
    try:
        req = urllib.request.Request(
            'http://127.0.0.1:8000/api/chat',
            data=json.dumps({'message': 'Check my current volume level.'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            chat_res = json.loads(response.read().decode('utf-8'))
            print(f"[OK] Audio Command Response: {chat_res.get('response')}")
            tool_calls = chat_res.get('tool_calls', [])
            print(f"     Tool Calls Count: {len(tool_calls)}")
            for tc in tool_calls:
                print(f"     -> Tool Name: {tc.get('name')}, Success: {tc.get('success')}")
    except Exception as e:
        print(f"[FAIL] Audio Command: {e}")

if __name__ == "__main__":
    run_integration_check()
