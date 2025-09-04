#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ランプ検知システム設定管理Webアプリ
Flask を使用してsetting.jsonを編集し、main.pyを再実行
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import subprocess
import threading
import time
import signal
import psutil
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'lamp_detection_system_secret_key'

# グローバル変数
main_process = None
main_process_thread = None

# ========================================
# 設定ファイル管理
# ========================================

def load_settings():
    """setting.jsonから設定を読み込む"""
    try:
        with open('setting.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"設定ファイルの読み込みエラー: {e}")
        return None

def save_settings(settings):
    """設定をsetting.jsonに保存"""
    try:
        with open('setting.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"設定ファイルの保存エラー: {e}")
        return False

def validate_settings(settings):
    """設定値のバリデーション"""
    errors = []
    
    # 座標の検証
    for color in ['orange', 'green']:
        coords = settings.get('coordinates', {}).get(color, {})
        if not all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
            errors.append(f"{color}の座標が不完全です")
        elif coords['x1'] >= coords['x2'] or coords['y1'] >= coords['y2']:
            errors.append(f"{color}の座標が無効です (x1 < x2, y1 < y2 である必要があります)")
    
    # 数値の検証
    numeric_checks = [
        ('detection.detection_interval_seconds', 1, 3600),
        ('detection.notification_threshold_minutes', 1, 120),
        ('detection.color_detection_threshold_percentage', 0, 100),
        ('camera.search_range', 1, 10)
    ]
    
    for key_path, min_val, max_val in numeric_checks:
        keys = key_path.split('.')
        value = settings
        try:
            for key in keys:
                value = value[key]
            if not (min_val <= value <= max_val):
                errors.append(f"{key_path}の値が範囲外です ({min_val}-{max_val})")
        except (KeyError, TypeError):
            errors.append(f"{key_path}が見つかりません")
    
    return errors

# ========================================
# main.py プロセス管理
# ========================================

def is_main_running():
    """main.pyが実行中かチェック"""
    global main_process
    return main_process is not None and main_process.poll() is None

def start_main_process():
    """main.pyを開始"""
    global main_process, main_process_thread
    
    if is_main_running():
        print("[INFO] main.pyは既に実行中です")
        return False
    
    try:
        # main.pyを別プロセスで実行
        main_process = subprocess.Popen(
            ['python', 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        print(f"[INFO] main.pyを開始しました (PID: {main_process.pid})")
        return True
    except Exception as e:
        print(f"[ERROR] main.pyの開始に失敗: {e}")
        return False

def stop_main_process():
    """main.pyを停止"""
    global main_process
    
    if not is_main_running():
        print("[INFO] main.pyは実行されていません")
        return True
    
    try:
        # プロセスを終了
        main_process.terminate()
        main_process.wait(timeout=10)
        print("[INFO] main.pyを正常に停止しました")
        main_process = None
        return True
    except subprocess.TimeoutExpired:
        # 強制終了
        main_process.kill()
        main_process.wait()
        print("[INFO] main.pyを強制終了しました")
        main_process = None
        return True
    except Exception as e:
        print(f"[ERROR] main.pyの停止に失敗: {e}")
        return False

def restart_main_process():
    """main.pyを再起動"""
    print("[INFO] main.pyを再起動中...")
    
    # 停止
    if is_main_running():
        stop_main_process()
        time.sleep(2)  # 少し待機
    
    # 開始
    return start_main_process()

# ========================================
# Flaskルート
# ========================================

@app.route('/')
def index():
    """メインページ"""
    settings = load_settings()
    main_running = is_main_running()
    
    return render_template('index.html', 
                         settings=settings, 
                         main_running=main_running,
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/settings', methods=['GET'])
def get_settings_api():
    """設定を取得するAPI"""
    settings = load_settings()
    if settings:
        return jsonify({'success': True, 'data': settings})
    else:
        return jsonify({'success': False, 'error': '設定の読み込みに失敗しました'}), 500

@app.route('/api/settings', methods=['POST'])
def update_settings_api():
    """設定を更新するAPI"""
    try:
        new_settings = request.json
        
        # バリデーション
        errors = validate_settings(new_settings)
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # 保存
        if save_settings(new_settings):
            return jsonify({'success': True, 'message': '設定を保存しました'})
        else:
            return jsonify({'success': False, 'error': '設定の保存に失敗しました'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/main/status', methods=['GET'])
def get_main_status():
    """main.pyの実行状態を取得"""
    running = is_main_running()
    pid = main_process.pid if main_process else None
    
    return jsonify({
        'running': running,
        'pid': pid,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/main/restart', methods=['POST'])
def restart_main():
    """main.pyを再起動"""
    try:
        success = restart_main_process()
        if success:
            return jsonify({'success': True, 'message': 'main.pyを再起動しました'})
        else:
            return jsonify({'success': False, 'error': 'main.pyの再起動に失敗しました'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/main/start', methods=['POST'])
def start_main():
    """main.pyを開始"""
    try:
        success = start_main_process()
        if success:
            return jsonify({'success': True, 'message': 'main.pyを開始しました'})
        else:
            return jsonify({'success': False, 'error': 'main.pyの開始に失敗しました'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/main/stop', methods=['POST'])
def stop_main():
    """main.pyを停止"""
    try:
        success = stop_main_process()
        if success:
            return jsonify({'success': True, 'message': 'main.pyを停止しました'})
        else:
            return jsonify({'success': False, 'error': 'main.pyの停止に失敗しました'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/settings')
def settings_page():
    """設定編集ページ"""
    settings = load_settings()
    return render_template('settings.html', settings=settings)

# ========================================
# アプリケーション開始
# ========================================

def cleanup_on_exit():
    """終了時のクリーンアップ"""
    global main_process
    if main_process:
        print("[INFO] Flaskアプリ終了時にmain.pyを停止中...")
        stop_main_process()

if __name__ == '__main__':
    print("=" * 60)
    print("🌐 ランプ検知システム設定管理Webアプリ")
    print("=" * 60)
    print("アクセスURL: http://localhost:5000")
    print("設定編集: http://localhost:5000/settings")
    print("終了: Ctrl+C")
    print("=" * 60)
    
    # 終了時のクリーンアップを登録
    import atexit
    atexit.register(cleanup_on_exit)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n[INFO] Flaskアプリを終了します")
        cleanup_on_exit()
