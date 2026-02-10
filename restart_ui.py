#!/usr/bin/env python3
"""
Streamlit UI 重啟腳本
用法: python restart_ui.py
"""

import subprocess
import sys
import os
import time
import signal

def kill_streamlit():
    """Kill existing streamlit processes"""
    print("🔍 正在尋找現有的 Streamlit 進程...")
    try:
        # Windows
        result = subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *streamlit*'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 已終止現有 Streamlit 進程")
        else:
            # Try alternative method
            result = subprocess.run(['taskkill', '/F', '/FI', 'COMMANDLINE eq *streamlit*'], 
                                  capture_output=True, text=True)
    except Exception as e:
        print(f"⚠️ 終止進程時發生問題（這是正常的如果沒有運行中的進程）: {e}")
    
    # Wait a moment
    time.sleep(2)

def clear_cache():
    """Clear Streamlit cache"""
    print("🧹 清除 Streamlit 快取...")
    cache_dirs = [
        '.streamlit/cache',
        '__pycache__',
        'src/__pycache__',
        'src/config/__pycache__',
        'src/etl/__pycache__',
        'src/models/__pycache__',
        'src/optimization/__pycache__'
    ]
    
    import shutil
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print(f"  ✓ 已清除 {cache_dir}")
            except Exception as e:
                print(f"  ⚠️ 無法清除 {cache_dir}: {e}")

def start_streamlit():
    """Start Streamlit"""
    print("\n🚀 啟動 Streamlit UI...")
    print("=" * 50)
    
    # Set environment variable to disable file watcher (prevents some caching issues)
    env = os.environ.copy()
    env['STREAMLIT_SERVER_FILEWATCHER_TYPE'] = 'none'
    
    try:
        subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'etl_ui.py'], 
                      env=env, check=True)
    except KeyboardInterrupt:
        print("\n👋 已停止 Streamlit")
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        print("\n請手動執行: streamlit run etl_ui.py")

def main():
    print("=" * 50)
    print("Streamlit UI 重啟工具")
    print("=" * 50)
    
    # Step 1: Kill existing processes
    kill_streamlit()
    
    # Step 2: Clear cache
    clear_cache()
    
    # Step 3: Start fresh
    start_streamlit()

if __name__ == "__main__":
    main()
