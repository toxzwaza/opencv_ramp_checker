#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ランプ検知システム設定管理Webアプリ
Flask を使用してsetting.jsonを編集し、main.pyを再実行
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
import json
import os
import subprocess
import threading
import time
import signal
import psutil
import cv2
import numpy as np
from datetime import datetime
import base64

app = Flask(__name__)
app.secret_key = 'lamp_detection_system_secret_key'

# グローバル変数
main_process = None
main_process_thread = None
camera_feed = None
camera_thread = None
camera_running = False

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
        # main.pyを別プロセスで実行（カメラモードで自動実行）
        # 環境変数でメニュー選択を自動化
        env = os.environ.copy()
        env['LAMP_AUTO_MODE'] = '4'  # ライブカメラモードを自動選択
        
        main_process = subprocess.Popen(
            ['python', 'main_auto.py'],  # 自動実行版を使用
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,  # Windowsで新しいコンソールを作成
            stdout=None,  # 出力をブロックしない
            stderr=None
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

@app.route('/coordinates')
def coordinates_page():
    """座標設定ページ"""
    settings = load_settings()
    main_running = is_main_running()
    return render_template('coordinates.html', settings=settings, main_running=main_running)

@app.route('/api/coordinates/start', methods=['POST'])
def start_coordinate_setter():
    """座標設定ツールを開始"""
    try:
        # main.pyが実行中の場合は停止
        if is_main_running():
            stop_main_process()
            time.sleep(2)
        
        # 座標設定ツールを開始
        coord_process = subprocess.Popen(
            ['python', 'coordinate_setter.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        return jsonify({
            'success': True, 
            'message': '座標設定ツールを開始しました',
            'pid': coord_process.pid
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/coordinates/preview', methods=['GET'])
def preview_coordinates():
    """現在の座標設定をプレビュー"""
    try:
        # coordinate_setter.pyのプレビュー機能を使用
        result = subprocess.run(
            ['python', 'coordinate_setter.py', '--preview'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr or 'プレビューの実行に失敗しました'
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/coordinate_preview_feed')
def coordinate_preview_feed():
    """座標プレビュー用の映像フィード"""
    try:
        # カメラから1フレーム取得
        camera_index = find_available_camera()
        if camera_index is None:
            error_frame = create_error_frame()
            _, buffer = cv2.imencode('.jpg', error_frame)
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            error_frame = create_error_frame()
            _, buffer = cv2.imencode('.jpg', error_frame)
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # フレームを取得
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            error_frame = create_error_frame()
            _, buffer = cv2.imencode('.jpg', error_frame)
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # 座標プレビューオーバーレイを追加
        frame_with_coordinates = add_coordinate_preview_overlay(frame)
        
        # JPEGエンコード
        _, buffer = cv2.imencode('.jpg', frame_with_coordinates, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return Response(buffer.tobytes(), mimetype='image/jpeg')
        
    except Exception as e:
        print(f"[ERROR] 座標プレビューエラー: {e}")
        error_frame = create_error_frame()
        _, buffer = cv2.imencode('.jpg', error_frame)
        return Response(buffer.tobytes(), mimetype='image/jpeg')

def add_coordinate_preview_overlay(frame):
    """座標プレビュー用のオーバーレイを追加"""
    overlay_frame = frame.copy()
    settings = load_settings()
    
    if not settings:
        return overlay_frame
    
    # 座標を取得
    coordinates = settings.get('coordinates', {})
    
    # オレンジランプの座標
    orange_coords = coordinates.get('orange', {})
    if all(key in orange_coords for key in ['x1', 'y1', 'x2', 'y2']):
        x1, y1, x2, y2 = orange_coords['x1'], orange_coords['y1'], orange_coords['x2'], orange_coords['y2']
        
        # オレンジ色の矩形を描画
        cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), (0, 165, 255), 3)  # オレンジ色 (BGR)
        
        # ラベルを描画
        label_text = "ORANGE LAMP"
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_width, text_height), baseline = cv2.getTextSize(label_text, font, 0.6, 2)
        
        # ラベル背景
        label_y = max(y1 - 10, text_height + 5)
        cv2.rectangle(overlay_frame, (x1, label_y - text_height - 5), 
                     (x1 + text_width + 10, label_y + 5), (0, 165, 255), -1)
        
        # ラベルテキスト
        cv2.putText(overlay_frame, label_text, (x1 + 5, label_y), 
                   font, 0.6, (255, 255, 255), 2)
        
        # サイズ情報
        size_text = f"{x2-x1}x{y2-y1}"
        cv2.putText(overlay_frame, size_text, (x1, y2 + 20), 
                   font, 0.5, (0, 165, 255), 2)
    
    # 緑ランプの座標
    green_coords = coordinates.get('green', {})
    if all(key in green_coords for key in ['x1', 'y1', 'x2', 'y2']):
        x1, y1, x2, y2 = green_coords['x1'], green_coords['y1'], green_coords['x2'], green_coords['y2']
        
        # 緑色の矩形を描画
        cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)  # 緑色 (BGR)
        
        # ラベルを描画
        label_text = "GREEN LAMP"
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_width, text_height), baseline = cv2.getTextSize(label_text, font, 0.6, 2)
        
        # ラベル背景
        label_y = max(y1 - 10, text_height + 5)
        cv2.rectangle(overlay_frame, (x1, label_y - text_height - 5), 
                     (x1 + text_width + 10, label_y + 5), (0, 255, 0), -1)
        
        # ラベルテキスト
        cv2.putText(overlay_frame, label_text, (x1 + 5, label_y), 
                   font, 0.6, (0, 0, 0), 2)
        
        # サイズ情報
        size_text = f"{x2-x1}x{y2-y1}"
        cv2.putText(overlay_frame, size_text, (x1, y2 + 20), 
                   font, 0.5, (0, 255, 0), 2)
    
    # 全体的な情報を表示
    info_text = "COORDINATE PREVIEW"
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(info_text, font, 0.8, 2)
    
    # 情報背景
    cv2.rectangle(overlay_frame, (10, 10), 
                 (text_width + 20, text_height + 20), (100, 100, 100), -1)
    
    # 情報テキスト
    cv2.putText(overlay_frame, info_text, (15, text_height + 15), 
               font, 0.8, (255, 255, 255), 2)
    
    # 時刻表示
    time_text = datetime.now().strftime('%H:%M:%S')
    cv2.putText(overlay_frame, time_text, (15, frame.shape[0] - 15), 
               font, 0.6, (255, 255, 255), 2)
    
    return overlay_frame

# ========================================
# カメラストリーミング機能
# ========================================

def find_available_camera():
    """利用可能なカメラデバイスを検索"""
    settings = load_settings()
    search_range = settings.get('camera', {}).get('search_range', 5) if settings else 5
    
    print(f"[CAMERA] カメラデバイスを検索中... (範囲: 0-{search_range-1})")
    
    for camera_index in range(search_range):
        print(f"[CAMERA] カメラデバイス {camera_index} をテスト中...")
        try:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"[FOUND] カメラデバイス {camera_index} が利用可能です (解像度: {frame.shape[1]}x{frame.shape[0]})")
                    cap.release()
                    return camera_index
                else:
                    print(f"[FAIL] カメラデバイス {camera_index} - フレーム取得失敗")
                cap.release()
            else:
                print(f"[FAIL] カメラデバイス {camera_index} - デバイス開けず")
        except Exception as e:
            print(f"[ERROR] カメラデバイス {camera_index} - エラー: {e}")
    
    print("[ERROR] 利用可能なカメラデバイスが見つかりません")
    return None

def generate_camera_frames():
    """カメラフレームを生成（ストリーミング用）"""
    global camera_running
    
    print("[STREAM] カメラストリーミング開始")
    camera_index = find_available_camera()
    if camera_index is None:
        print("[STREAM] カメラが見つからないため、エラーフレームを生成")
        # エラー用のダミーフレームを生成
        error_frame = create_error_frame()
        _, buffer = cv2.imencode('.jpg', error_frame)
        frame_bytes = buffer.tobytes()
        
        while camera_running:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(1)
        return
    
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[STREAM] カメラデバイス {camera_index} を開けませんでした")
        return
    
    try:
        while camera_running:
            ret, frame = cap.read()
            if not ret:
                break
            
            # フレームサイズを調整（Webページ表示用）
            height, width = frame.shape[:2]
            if width > 640:
                scale = 640 / width
                new_width = 640
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
            
            # 現在の検知状態をオーバーレイ
            frame_with_status = add_status_overlay_web(frame)
            
            # JPEGエンコード
            _, buffer = cv2.imencode('.jpg', frame_with_status, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            
            # ストリーミング形式で出力
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.03)  # 約30FPS
            
    except Exception as e:
        print(f"[ERROR] カメラストリーミングエラー: {e}")
    finally:
        cap.release()

def load_detection_logs():
    """data.csvから最新の検知ログを読み込み"""
    try:
        if not os.path.exists('data.csv'):
            return []
        
        import csv
        logs = []
        with open('data.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                logs.append(row)
        
        # 最新5件を返す
        return logs[-5:] if logs else []
    except Exception as e:
        print(f"[ERROR] ログ読み込みエラー: {e}")
        return []

def add_status_overlay_web(frame):
    """Web表示用のステータスオーバーレイを追加（main.pyと同様の表示）"""
    overlay_frame = frame.copy()
    
    # main.pyの表示と同様のオーバーレイを作成
    y_offset = 25
    line_height = 20
    
    # タイトル
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    def draw_text_bg(img, text, pos, font_scale=0.35, color=(255, 255, 255), bg_color=(0, 0, 0), thickness=1):
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        x, y = pos
        cv2.rectangle(img, (x - 5, y - text_height - 5), 
                     (x + text_width + 5, y + baseline + 5), bg_color, -1)
        cv2.putText(img, text, pos, font, font_scale, color, thickness)
    
    # タイトル
    draw_text_bg(overlay_frame, "LAMP DETECTION SYSTEM", (20, y_offset), 
                font_scale=0.5, color=(255, 255, 255), bg_color=(0, 100, 200))
    y_offset += line_height + 5
    
    # 現在時刻
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    draw_text_bg(overlay_frame, f"TIME: {time_str}", (20, y_offset), 
                color=(255, 255, 255), bg_color=(50, 50, 50))
    y_offset += line_height
    
    # 実行状態
    main_running = is_main_running()
    if main_running:
        mode_text = "[WEB MONITORING]"
        mode_color = (0, 255, 255)
        mode_bg = (100, 0, 100)
    else:
        mode_text = "[PREVIEW MODE]"
        mode_color = (255, 255, 255)
        mode_bg = (50, 50, 50)
    
    draw_text_bg(overlay_frame, mode_text, (20, y_offset), 
                color=mode_color, bg_color=mode_bg)
    y_offset += line_height + 5
    
    # 検知ログの表示
    detection_logs = load_detection_logs()
    if detection_logs:
        draw_text_bg(overlay_frame, "RECENT DETECTIONS:", (20, y_offset), 
                    font_scale=0.4, color=(255, 255, 255), bg_color=(100, 100, 0))
        y_offset += line_height
        
        for log in detection_logs:
            if log.get('detection_result'):
                log_text = f"{log['timestamp'][-8:]} - {log['detection_result']}"
                log_color = (0, 165, 255) if log['detection_result'] == 'オレンジ' else (0, 255, 0)
                draw_text_bg(overlay_frame, log_text, (30, y_offset), 
                           font_scale=0.3, color=log_color, bg_color=(30, 30, 30))
                y_offset += 15
    
    # 操作説明
    y_offset += 5
    draw_text_bg(overlay_frame, "Web control available below", (20, y_offset), 
                font_scale=0.3, color=(255, 255, 255), bg_color=(100, 0, 0))
    
    return overlay_frame

def create_error_frame():
    """カメラエラー時のダミーフレームを作成"""
    # 640x480の黒いフレームを作成
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # エラーメッセージを描画
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # 背景矩形
    cv2.rectangle(frame, (50, 200), (590, 280), (50, 50, 50), -1)
    
    # エラーテキスト
    error_texts = [
        "Camera Not Available",
        "Please check camera connection",
        "or try restarting the system"
    ]
    
    y_offset = 230
    for text in error_texts:
        (text_width, _), _ = cv2.getTextSize(text, font, 0.8, 2)
        x_offset = (640 - text_width) // 2
        cv2.putText(frame, text, (x_offset, y_offset), font, 0.8, (0, 0, 255), 2)
        y_offset += 30
    
    return frame

def check_camera_conflicts():
    """カメラの競合状態をチェック"""
    conflicts = []
    
    # main.pyプロセスがカメラを使用中かチェック
    if is_main_running():
        conflicts.append("main.pyがカメラを使用中の可能性があります")
    
    # 他のOpenCVプロセスをチェック
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if ('python' in cmdline.lower() and 
                        ('cv2' in cmdline or 'opencv' in cmdline) and 
                        proc.info['pid'] != os.getpid()):
                        conflicts.append(f"他のOpenCVプロセスが実行中: PID {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass
    
    return conflicts

def start_camera_feed():
    """カメラフィードを開始"""
    global camera_running, camera_thread
    
    if camera_running:
        return True
    
    camera_running = True
    camera_thread = threading.Thread(target=lambda: None)  # ダミー
    camera_thread.start()
    
    return True

def stop_camera_feed():
    """カメラフィードを停止"""
    global camera_running, camera_thread
    
    camera_running = False
    if camera_thread and camera_thread.is_alive():
        camera_thread.join(timeout=2)
    
    return True

@app.route('/video_feed')
def video_feed():
    """画像ファイルベースの映像フィード"""
    # main.pyが実行中の場合のみ画像を提供
    if not is_main_running():
        print("[STREAM] main.pyが停止中のため、映像を提供しません")
        return Response("", mimetype='text/plain')
    
    # streaming/current_frame.jpgを読み込んで返す
    try:
        current_frame_path = os.path.join("streaming", "current_frame.jpg")
        
        if os.path.exists(current_frame_path):
            # ファイルの更新時刻をチェック
            file_time = os.path.getmtime(current_frame_path)
            current_time = time.time()
            
            # 5分以上古い場合は「接続なし」画像を表示
            if current_time - file_time > 300:  # 5分
                print(f"[STREAM] フレームが古すぎます ({current_time - file_time:.1f}秒前)")
                error_frame = create_no_connection_frame()
                _, buffer = cv2.imencode('.jpg', error_frame)
                return Response(buffer.tobytes(), mimetype='image/jpeg')
            
            # 画像ファイルを読み込んで返す
            with open(current_frame_path, 'rb') as f:
                image_data = f.read()
            
            return Response(image_data, mimetype='image/jpeg')
        else:
            print("[STREAM] current_frame.jpgが見つかりません")
            # 「待機中」画像を生成
            waiting_frame = create_waiting_frame()
            _, buffer = cv2.imencode('.jpg', waiting_frame)
            return Response(buffer.tobytes(), mimetype='image/jpeg')
            
    except Exception as e:
        print(f"[ERROR] 映像フィード エラー: {e}")
        error_frame = create_error_frame()
        _, buffer = cv2.imencode('.jpg', error_frame)
        return Response(buffer.tobytes(), mimetype='image/jpeg')

def create_waiting_frame():
    """待機中フレームを作成"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # 背景矩形
    cv2.rectangle(frame, (50, 200), (590, 280), (0, 100, 200), -1)
    
    # 待機メッセージ
    waiting_texts = [
        "Waiting for camera feed...",
        "main.py is starting up",
        "Please wait a moment"
    ]
    
    y_offset = 230
    for text in waiting_texts:
        (text_width, _), _ = cv2.getTextSize(text, font, 0.8, 2)
        x_offset = (640 - text_width) // 2
        cv2.putText(frame, text, (x_offset, y_offset), font, 0.8, (255, 255, 255), 2)
        y_offset += 30
    
    return frame

def create_no_connection_frame():
    """接続なしフレームを作成"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # 背景矩形
    cv2.rectangle(frame, (50, 200), (590, 280), (0, 0, 100), -1)
    
    # 接続なしメッセージ
    no_conn_texts = [
        "No recent camera feed",
        "System may have stopped",
        "Check main.py status"
    ]
    
    y_offset = 230
    for text in no_conn_texts:
        (text_width, _), _ = cv2.getTextSize(text, font, 0.8, 2)
        x_offset = (640 - text_width) // 2
        cv2.putText(frame, text, (x_offset, y_offset), font, 0.8, (255, 255, 0), 2)
        y_offset += 30
    
    return frame

def create_error_frame():
    """カメラエラー時のダミーフレームを作成"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # 背景矩形
    cv2.rectangle(frame, (50, 200), (590, 280), (50, 50, 50), -1)
    
    # エラーテキスト
    error_texts = [
        "Camera Error",
        "Please check camera connection",
        "or restart the system"
    ]
    
    y_offset = 230
    for text in error_texts:
        (text_width, _), _ = cv2.getTextSize(text, font, 0.8, 2)
        x_offset = (640 - text_width) // 2
        cv2.putText(frame, text, (x_offset, y_offset), font, 0.8, (0, 0, 255), 2)
        y_offset += 30
    
    return frame

@app.route('/api/camera/debug', methods=['GET'])
def camera_debug():
    """カメラデバッグ情報を取得"""
    try:
        debug_info = {
            'main_running': is_main_running(),
            'camera_running': camera_running,
            'available_camera': find_available_camera(),
            'conflicts': check_camera_conflicts(),
            'settings_loaded': load_settings() is not None
        }
        
        return jsonify({'success': True, 'debug_info': debug_info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/camera/start', methods=['POST'])
def start_camera_api():
    """カメラフィードを開始するAPI"""
    try:
        success = start_camera_feed()
        if success:
            return jsonify({'success': True, 'message': 'カメラフィードを開始しました'})
        else:
            return jsonify({'success': False, 'error': 'カメラフィードの開始に失敗しました'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/camera/stop', methods=['POST'])
def stop_camera_api():
    """カメラフィードを停止するAPI"""
    try:
        success = stop_camera_feed()
        if success:
            return jsonify({'success': True, 'message': 'カメラフィードを停止しました'})
        else:
            return jsonify({'success': False, 'error': 'カメラフィードの停止に失敗しました'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========================================
# アプリケーション開始
# ========================================

def cleanup_on_exit():
    """終了時のクリーンアップ"""
    global main_process, camera_running
    
    # カメラフィードを停止
    stop_camera_feed()
    
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
