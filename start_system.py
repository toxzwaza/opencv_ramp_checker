#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ランプ検知システム統合起動スクリプト
Flask WebアプリとOpenCV監視システムを管理
"""

import subprocess
import time
import os
import signal
import sys
import threading
from datetime import datetime

class SystemManager:
    def __init__(self):
        self.flask_process = None
        self.main_process = None
        self.running = True
    
    def start_flask_app(self):
        """Flask Webアプリを開始"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Flask Webアプリを開始中...")
            self.flask_process = subprocess.Popen(
                ['python', 'app.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Flask Webアプリが開始されました (PID: {self.flask_process.pid})")
            print("🌐 Webアプリ: http://localhost:5000")
            return True
        except Exception as e:
            print(f"[ERROR] Flask Webアプリの開始に失敗: {e}")
            return False
    
    def start_main_app(self):
        """main.pyを開始"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] カメラ監視システムを開始中...")
            
            # 環境変数でライブカメラモードを指定
            env = os.environ.copy()
            env['LAMP_AUTO_MODE'] = '4'
            
            self.main_process = subprocess.Popen(
                ['python', 'main_auto.py'],
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
                stdout=None,
                stderr=None
            )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] カメラ監視システムが開始されました (PID: {self.main_process.pid})")
            return True
        except Exception as e:
            print(f"[ERROR] カメラ監視システムの開始に失敗: {e}")
            return False
    
    def stop_all(self):
        """全プロセスを停止"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] システム終了処理を開始...")
        
        # main.pyを停止
        if self.main_process and self.main_process.poll() is None:
            try:
                self.main_process.terminate()
                self.main_process.wait(timeout=10)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] カメラ監視システムを停止しました")
            except subprocess.TimeoutExpired:
                self.main_process.kill()
                self.main_process.wait()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] カメラ監視システムを強制終了しました")
            except Exception as e:
                print(f"[ERROR] カメラ監視システムの停止に失敗: {e}")
        
        # Flask Webアプリを停止
        if self.flask_process and self.flask_process.poll() is None:
            try:
                self.flask_process.terminate()
                self.flask_process.wait(timeout=5)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Flask Webアプリを停止しました")
            except subprocess.TimeoutExpired:
                self.flask_process.kill()
                self.flask_process.wait()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Flask Webアプリを強制終了しました")
            except Exception as e:
                print(f"[ERROR] Flask Webアプリの停止に失敗: {e}")
        
        self.running = False
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 全システムの終了が完了しました")
    
    def monitor_processes(self):
        """プロセスの状態を監視"""
        while self.running:
            try:
                # Flask Webアプリの監視
                if self.flask_process and self.flask_process.poll() is not None:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WARNING] Flask Webアプリが予期せず終了しました")
                    self.flask_process = None
                
                # main.pyの監視
                if self.main_process and self.main_process.poll() is not None:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WARNING] カメラ監視システムが予期せず終了しました")
                    self.main_process = None
                
                time.sleep(5)  # 5秒毎にチェック
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] プロセス監視エラー: {e}")
                time.sleep(5)
    
    def run(self):
        """システム全体を実行"""
        try:
            print("=" * 80)
            print("🚦 ランプ検知システム統合管理")
            print("=" * 80)
            print("このスクリプトは以下のサービスを管理します:")
            print("1. Flask Webアプリ (http://localhost:5000)")
            print("2. OpenCVカメラ監視システム (main.py)")
            print("=" * 80)
            
            # Flask Webアプリを開始
            if not self.start_flask_app():
                return False
            
            # 少し待機
            time.sleep(3)
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] システム起動完了!")
            print("🌐 Webアプリにアクセス: http://localhost:5000")
            print("⚙️ 設定編集: http://localhost:5000/settings")
            print("📍 座標設定: http://localhost:5000/coordinates")
            print("📝 注意: カメラ監視システムはWebアプリから手動で開始してください")
            print("🛑 終了: Ctrl+C")
            print("=" * 80)
            
            # プロセス監視を開始
            monitor_thread = threading.Thread(target=self.monitor_processes)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # メインループ
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 終了要求を受信しました")
        except Exception as e:
            print(f"[ERROR] システム実行エラー: {e}")
        finally:
            self.stop_all()

def signal_handler(sig, frame):
    """シグナルハンドラー"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 終了シグナルを受信しました")
    sys.exit(0)

if __name__ == '__main__':
    # シグナルハンドラーを設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # システム管理を開始
    manager = SystemManager()
    manager.run()
