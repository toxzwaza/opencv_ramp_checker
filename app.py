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
from datetime import datetime, timedelta
import base64
import csv
import matplotlib
matplotlib.use('Agg')  # GUI不要のバックエンドを使用
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# matplotlib の設定
matplotlib.rcParams['axes.formatter.limits'] = [-5, 6]
matplotlib.rcParams['axes.formatter.use_mathtext'] = True
# 図の最大数制限（警告を防ぐ）
matplotlib.rcParams['figure.max_open_warning'] = 50
from io import BytesIO
import pandas as pd

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

# ========================================
# 監視システム API（monitoring.htmlとbase.html用）
# ========================================

@app.route('/api/monitoring/status', methods=['GET'])
def get_monitoring_status():
    """監視システムの状態を取得"""
    try:
        running = is_main_running()
        pid = main_process.pid if main_process else None
        
        return jsonify({
            'running': running,
            'pid': pid,
            'timestamp': datetime.now().isoformat(),
            'uptime': None  # 将来的な拡張用
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    """監視システムを開始"""
    try:
        success = start_main_process()
        if success:
            return jsonify({'success': True, 'message': '監視システムを開始しました'})
        else:
            return jsonify({'success': False, 'message': '監視システムの開始に失敗しました'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'エラー: {str(e)}'})

@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    """監視システムを停止"""
    try:
        success = stop_main_process()
        if success:
            return jsonify({'success': True, 'message': '監視システムを停止しました'})
        else:
            return jsonify({'success': False, 'message': '監視システムの停止に失敗しました'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'エラー: {str(e)}'})

# ========================================
# 画像関連 API（monitoring.html用）
# ========================================

@app.route('/api/image/latest', methods=['GET'])
def get_latest_image():
    """最新の画像を取得"""
    try:
        # streaming/current_frame.jpgを確認
        current_frame_path = os.path.join("streaming", "current_frame.jpg")
        
        if os.path.exists(current_frame_path):
            # ファイルの更新時刻をチェック
            file_time = os.path.getmtime(current_frame_path)
            current_time = time.time()
            
            # 5分以上古い場合は「接続なし」画像を返す
            if current_time - file_time > 300:  # 5分
                error_frame = create_no_connection_frame()
                _, buffer = cv2.imencode('.jpg', error_frame)
                return Response(buffer.tobytes(), mimetype='image/jpeg')
            
            # 最新の画像ファイルを返す
            with open(current_frame_path, 'rb') as f:
                image_data = f.read()
            
            return Response(image_data, mimetype='image/jpeg')
        else:
            # 画像がない場合は「待機中」画像を返す
            waiting_frame = create_waiting_frame()
            _, buffer = cv2.imencode('.jpg', waiting_frame)
            return Response(buffer.tobytes(), mimetype='image/jpeg')
            
    except Exception as e:
        print(f"[ERROR] 最新画像取得エラー: {e}")
        error_frame = create_error_frame()
        _, buffer = cv2.imencode('.jpg', error_frame)
        return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route('/api/image/capture', methods=['POST'])
def capture_image():
    """カメラから画像をキャプチャ"""
    try:
        # sample_imgディレクトリが存在しない場合は作成
        sample_img_dir = "sample_img"
        if not os.path.exists(sample_img_dir):
            os.makedirs(sample_img_dir)
            print(f"[INFO] ディレクトリを作成しました: {sample_img_dir}")
        
        # カメラから画像をキャプチャ
        print("[DEBUG] カメラキャプチャ開始")
        camera_index = find_available_camera()
        if camera_index is None:
            print("[ERROR] カメラが見つかりません")
            return jsonify({'success': False, 'message': 'カメラが利用できません。カメラが接続されているか確認してください。'})
        
        print(f"[DEBUG] カメラデバイス {camera_index} を開いています...")
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f"[ERROR] カメラデバイス {camera_index} を開けませんでした")
            return jsonify({'success': False, 'message': f'カメラデバイス {camera_index} を開けませんでした'})
        
        try:
            print("[DEBUG] フレームを取得中...")
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] フレームを取得できませんでした")
                return jsonify({'success': False, 'message': 'フレームを取得できませんでした'})
            
            # タイムスタンプ付きのファイル名で保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            capture_filename = f"manual_capture_{timestamp}.png"
            capture_path = os.path.join(sample_img_dir, capture_filename)
            
            if cv2.imwrite(capture_path, frame):
                print(f"[SUCCESS] 画像をキャプチャしました: {capture_path}")
                return jsonify({
                    'success': True, 
                    'message': f'画像をキャプチャしました: {capture_filename}',
                    'filename': capture_filename,
                    'image_path': capture_path
                })
            else:
                return jsonify({'success': False, 'message': '画像の保存に失敗しました'})
                
        finally:
            cap.release()
            
    except Exception as e:
        print(f"[ERROR] 画像キャプチャエラー: {e}")
        return jsonify({'success': False, 'message': f'キャプチャエラー: {str(e)}'})

@app.route('/api/image/<filename>')
def serve_captured_image(filename):
    """キャプチャした画像を配信"""
    try:
        # sample_imgディレクトリから画像を配信
        sample_img_dir = "sample_img"
        image_path = os.path.join(sample_img_dir, filename)
        
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return Response(image_data, mimetype='image/png')
        else:
            print(f"[ERROR] 画像ファイルが見つかりません: {image_path}")
            return jsonify({'error': 'Image not found'}), 404
            
    except Exception as e:
        print(f"[ERROR] 画像配信エラー: {e}")
        return jsonify({'error': str(e)}), 500

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

@app.route('/monitoring')
def monitoring_page():
    """監視状況ページ"""
    settings = load_settings()
    main_running = is_main_running()
    return render_template('monitoring.html', 
                         settings=settings, 
                         main_running=main_running,
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/coordinates', methods=['GET'])
def get_coordinates_api():
    """現在の座標を取得するAPI"""
    try:
        settings = load_settings()
        if settings and 'coordinates' in settings:
            return jsonify({'success': True, 'coordinates': settings['coordinates']})
        else:
            # デフォルト座標を返す
            default_coordinates = {
                'orange': {'x1': 317, 'y1': 97, 'x2': 362, 'y2': 145},
                'green': {'x1': 315, 'y1': 130, 'x2': 363, 'y2': 180}
            }
            return jsonify({'success': True, 'coordinates': default_coordinates})
    except Exception as e:
        print(f"[ERROR] 座標取得API エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/coordinates', methods=['POST'])
def save_coordinates_api():
    """座標を保存するAPI"""
    try:
        coordinates = request.json
        
        # バリデーション
        if not coordinates or not isinstance(coordinates, dict):
            return jsonify({'success': False, 'message': '座標データが無効です'}), 400
        
        # 必要な座標データが含まれているかチェック
        required_colors = ['orange', 'green']
        required_keys = ['x1', 'y1', 'x2', 'y2']
        
        for color in required_colors:
            if color not in coordinates:
                return jsonify({'success': False, 'message': f'{color}の座標が見つかりません'}), 400
            
            coord_data = coordinates[color]
            for key in required_keys:
                if key not in coord_data:
                    return jsonify({'success': False, 'message': f'{color}の{key}座標が見つかりません'}), 400
                
                # 数値かどうかチェック
                if not isinstance(coord_data[key], (int, float)):
                    return jsonify({'success': False, 'message': f'{color}の{key}座標が数値ではありません'}), 400
        
        # 現在の設定を読み込み
        settings = load_settings()
        if not settings:
            # 設定ファイルが存在しない場合、デフォルト設定を作成
            settings = {
                "detection": {
                    "detection_interval_seconds": 5,
                    "notification_threshold_minutes": 5,
                    "color_detection_threshold_percentage": 70
                },
                "camera": {
                    "search_range": 5
                },
                "coordinates": {}
            }
        
        # 座標を更新
        settings['coordinates'] = coordinates
        
        # 設定を保存
        if save_settings(settings):
            return jsonify({'success': True, 'message': '座標を保存しました'})
        else:
            return jsonify({'success': False, 'message': '座標の保存に失敗しました'}), 500
            
    except Exception as e:
        print(f"[ERROR] 座標保存API エラー: {e}")
        return jsonify({'success': False, 'message': f'エラー: {str(e)}'}), 500

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
# オレンジ継続時間分析機能
# ========================================

def load_orange_durations():
    """data.csvからオレンジ継続時間データを読み込む"""
    csv_file = "data.csv"
    
    if not os.path.exists(csv_file):
        return []
    
    try:
        durations = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # デバッグモードのデータは無視し、通常モードのみを対象とする
                if (row['event_type'] == 'orange_end' and 
                    float(row['duration_seconds']) > 0 and 
                    row['debug_mode'] == 'normal'):
                    durations.append({
                        'timestamp': row['timestamp'],
                        'duration': float(row['duration_seconds']),
                        'mode': row['debug_mode'],
                        'orange_percentage': float(row['orange_percentage']),
                        'green_percentage': float(row['green_percentage'])
                    })
        return durations
    except Exception as e:
        print(f"❌ データ読み込みエラー: {e}")
        return []

def generate_duration_chart(durations):
    """継続時間の折れ線グラフを生成"""
    if not durations:
        return None
    
    print(f"[DEBUG] 継続時間グラフ: {len(durations)}件のデータを処理中")
    
    # 日本語フォント設定（matplotlib用）
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    # 図とサブプロットを作成
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle('Orange Lamp Duration Analysis', fontsize=16, fontweight='bold')
    
    # データを準備
    timestamps = [datetime.strptime(d['timestamp'], '%Y-%m-%d %H:%M:%S') for d in durations]
    duration_values = [d['duration'] for d in durations]
    orange_percentages = [d['orange_percentage'] for d in durations]
    
    print(f"[DEBUG] タイムスタンプ範囲: {timestamps[0]} - {timestamps[-1]}")
    print(f"[DEBUG] データ期間: {(timestamps[-1] - timestamps[0]).total_seconds() / 3600:.1f}時間")
    
    # 上部グラフ: 継続時間の推移
    ax1.plot(timestamps, duration_values, 'o-', color='orange', linewidth=2, markersize=6)
    ax1.set_title('Orange Duration Trend', fontsize=14)
    ax1.set_ylabel('Duration (seconds)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    
    # 平均線を追加
    avg_duration = sum(duration_values) / len(duration_values)
    ax1.axhline(y=avg_duration, color='red', linestyle='--', alpha=0.7, 
                label=f'Average: {avg_duration:.1f}s')
    ax1.legend()
    
    # 下部グラフ: オレンジ検知率の推移
    ax2.plot(timestamps, orange_percentages, 's-', color='darkorange', linewidth=2, markersize=5)
    ax2.set_title('Orange Detection Percentage', fontsize=14)
    ax2.set_ylabel('Detection %', fontsize=12)
    ax2.set_xlabel('Time', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 100)
    
    # X軸の日時フォーマット
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        
        # データの時間範囲を計算して適切な間隔を設定
        time_span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        print(f"[DEBUG] 時間範囲: {time_span_hours:.1f}時間")
        
        # 時間範囲に基づいて目盛り間隔を設定
        if time_span_hours <= 6:
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        elif time_span_hours <= 24:
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        elif time_span_hours <= 72:
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        elif time_span_hours <= 168:  # 1週間
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        else:
            # 非常に長い期間の場合は週単位
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
            
        # 目盛りの最大数を制限
        ax.locator_params(axis='x', nbins=10)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # レイアウト調整
    plt.tight_layout()
    
    # PNG形式でバイナリデータとして出力
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
    img_buffer.seek(0)
    
    # base64エンコード
    import base64
    chart_data = base64.b64encode(img_buffer.read()).decode()
    plt.close(fig)  # メモリリーク防止
    
    return chart_data

def calculate_statistics(durations):
    """統計情報を計算"""
    if not durations:
        return {}
    
    duration_values = [d['duration'] for d in durations]
    
    stats = {
        'total_count': len(durations),
        'average_duration': sum(duration_values) / len(duration_values),
        'min_duration': min(duration_values),
        'max_duration': max(duration_values),
        'total_orange_time': sum(duration_values)
    }
    
    # 最近の傾向（最新5件）
    if len(durations) >= 2:
        recent_durations = duration_values[-5:]
        stats['recent_average'] = sum(recent_durations) / len(recent_durations)
        
        # 改善傾向の分析
        if len(durations) >= 2:
            first_duration = duration_values[0]
            last_duration = duration_values[-1]
            stats['improvement'] = first_duration - last_duration
            stats['improvement_percentage'] = (stats['improvement'] / first_duration * 100) if first_duration > 0 else 0
    
    return stats

def load_all_detection_data():
    """data.csvから全ての検知データを時系列で読み込む"""
    csv_file = "data.csv"
    
    if not os.path.exists(csv_file):
        return []
    
    try:
        all_data = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 通常モードのデータのみを対象とする（デバッグデータは除外）
                if row['debug_mode'] == 'normal':
                    all_data.append({
                        'timestamp': row['timestamp'],
                        'event_type': row['event_type'],
                        'detection_result': row['detection_result'],
                        'orange_percentage': float(row['orange_percentage']) if row['orange_percentage'] else 0,
                        'green_percentage': float(row['green_percentage']) if row['green_percentage'] else 0,
                        'duration_seconds': float(row['duration_seconds']) if row['duration_seconds'] else 0,
                        'image_file': row.get('image_file', '')
                    })
        return all_data
    except Exception as e:
        print(f"❌ 全データ読み込みエラー: {e}")
        return []

def generate_gantt_chart(all_data, hours=24):
    """ガントチャート風のタイムライングラフを生成"""
    if not all_data:
        return None
    
    # 日本語フォント設定
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    # 最新データから指定時間分のデータを抽出
    if all_data:
        latest_time = datetime.strptime(all_data[-1]['timestamp'], '%Y-%m-%d %H:%M:%S')
        start_time = latest_time - timedelta(hours=hours)
        
        # 指定時間範囲内のデータをフィルタ
        filtered_data = []
        for data in all_data:
            data_time = datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
            if data_time >= start_time:
                filtered_data.append(data)
    else:
        filtered_data = all_data
    
    if not filtered_data:
        return None
    
    # 図を作成
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    fig.suptitle(f'Lamp Detection Timeline (Last {hours} Hours)', fontsize=16, fontweight='bold')
    
    # 時系列データを処理してガントチャート用に変換
    timeline_data = []
    current_state = None
    state_start = None
    
    for i, data in enumerate(filtered_data):
        timestamp = datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
        detection = data['detection_result']
        
        # 状態変化を検出
        if detection != current_state:
            # 前の状態を終了
            if current_state is not None and state_start is not None:
                timeline_data.append({
                    'start': state_start,
                    'end': timestamp,
                    'state': current_state,
                    'duration': (timestamp - state_start).total_seconds() / 60  # 分単位
                })
            
            # 新しい状態を開始
            current_state = detection
            state_start = timestamp
        
        # 最後のデータの場合は現在時刻まで延長
        if i == len(filtered_data) - 1:
            end_time = timestamp + timedelta(minutes=1)  # 1分間延長
            if current_state is not None and state_start is not None:
                timeline_data.append({
                    'start': state_start,
                    'end': end_time,
                    'state': current_state,
                    'duration': (end_time - state_start).total_seconds() / 60
                })
    
    # ガントチャートを描画
    y_pos = 0.5
    bar_height = 0.4
    
    for segment in timeline_data:
        start_time = segment['start']
        duration_hours = segment['duration'] / 60  # 時間単位に変換
        
        # 色の設定
        if segment['state'] == 'オレンジ':
            color = '#FF8C00'  # オレンジ色
            alpha = 0.8
        elif segment['state'] == '緑':
            color = '#32CD32'  # 緑色
            alpha = 0.8
        else:  # 不明
            color = '#808080'  # グレー
            alpha = 0.5
        
        # バーを描画
        ax.barh(y_pos, duration_hours, left=start_time, height=bar_height, 
                color=color, alpha=alpha, edgecolor='black', linewidth=0.5)
        
        # 長い区間にはラベルを追加
        if duration_hours > 0.5:  # 30分以上の場合
            label_x = start_time + timedelta(hours=duration_hours/2)
            label_text = f"{segment['state']}\n{segment['duration']:.1f}min"
            ax.text(label_x, y_pos, label_text, ha='center', va='center', 
                   fontsize=8, fontweight='bold', color='white')
    
    # 軸の設定
    ax.set_ylim(0, 1)
    ax.set_ylabel('Detection State', fontsize=12)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_title(f'Color Detection Timeline', fontsize=14)
    
    # Y軸のラベルを非表示
    ax.set_yticks([])
    
    # X軸の日時フォーマット
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
    
    # 時間範囲に応じて適切な間隔を設定
    print(f"[DEBUG] ガントチャート時間範囲: {hours}時間")
    if hours <= 6:
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    elif hours <= 24:
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    elif hours <= 72:
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    elif hours <= 168:  # 1週間
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    else:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    
    # 目盛りの最大数を制限
    ax.locator_params(axis='x', nbins=10)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # グリッドを追加
    ax.grid(True, axis='x', alpha=0.3)
    
    # 凡例を追加
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#FF8C00', alpha=0.8, label='オレンジ'),
        Patch(facecolor='#32CD32', alpha=0.8, label='緑'),
        Patch(facecolor='#808080', alpha=0.5, label='不明')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    # レイアウト調整
    plt.tight_layout()
    
    # PNG形式でバイナリデータとして出力
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
    img_buffer.seek(0)
    
    # base64エンコード
    import base64
    chart_data = base64.b64encode(img_buffer.read()).decode()
    plt.close(fig)  # メモリリーク防止
    
    return chart_data

@app.route('/analysis')
def analysis_page():
    """オレンジ継続時間分析ページ"""
    try:
        print("[DEBUG] 分析ページ開始")
        
        # データを読み込み
        durations = load_orange_durations()
        print(f"[DEBUG] 継続時間データ: {len(durations)}件")
        
        all_data = load_all_detection_data()
        print(f"[DEBUG] 全データ: {len(all_data)}件")
        
        # 統計情報を計算
        stats = calculate_statistics(durations)
        print(f"[DEBUG] 統計情報計算完了")
        
        # グラフを生成
        chart_data = None
        gantt_chart_data = None
        
        if durations:
            print(f"[DEBUG] 継続時間グラフ生成開始")
            try:
                chart_data = generate_duration_chart(durations)
                print(f"[DEBUG] 継続時間グラフ生成完了")
            except Exception as chart_error:
                print(f"[ERROR] 継続時間グラフエラー: {chart_error}")
                import traceback
                traceback.print_exc()
                # エラーが発生した場合はグラフなしで続行
                chart_data = None
        
        if all_data:
            print(f"[DEBUG] ガントチャート生成開始")
            try:
                gantt_chart_data = generate_gantt_chart(all_data, hours=24)
                print(f"[DEBUG] ガントチャート生成完了")
            except Exception as gantt_error:
                print(f"[ERROR] ガントチャートエラー: {gantt_error}")
                import traceback
                traceback.print_exc()
        
        print(f"[DEBUG] テンプレート描画開始")
        return render_template('analysis.html', 
                             durations=durations,
                             stats=stats,
                             chart_data=chart_data,
                             gantt_chart_data=gantt_chart_data,
                             current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
    except Exception as e:
        print(f"[ERROR] 分析ページエラー: {e}")
        import traceback
        traceback.print_exc()
        return render_template('analysis.html', 
                             durations=[],
                             stats={},
                             chart_data=None,
                             gantt_chart_data=None,
                             error=str(e),
                             current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/analysis/data', methods=['GET'])
def get_analysis_data():
    """分析データをJSON形式で取得するAPI"""
    try:
        durations = load_orange_durations()
        stats = calculate_statistics(durations)
        
        return jsonify({
            'success': True,
            'data': {
                'durations': durations,
                'statistics': stats,
                'total_records': len(durations)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analysis/chart', methods=['GET'])
def get_analysis_chart():
    """分析グラフを取得するAPI"""
    try:
        durations = load_orange_durations()
        
        if not durations:
            return jsonify({'success': False, 'error': 'データが見つかりません'}), 404
        
        chart_data = generate_duration_chart(durations)
        
        if chart_data:
            return jsonify({'success': True, 'chart_data': chart_data})
        else:
            return jsonify({'success': False, 'error': 'グラフの生成に失敗しました'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analysis/gantt', methods=['GET'])
def get_gantt_chart():
    """ガントチャートを取得するAPI"""
    try:
        # URLパラメータから時間範囲を取得（デフォルトは24時間）
        hours = int(request.args.get('hours', 24))
        hours = max(1, min(168, hours))  # 1時間から1週間までに制限
        
        all_data = load_all_detection_data()
        
        if not all_data:
            return jsonify({'success': False, 'error': 'データが見つかりません'}), 404
        
        gantt_chart_data = generate_gantt_chart(all_data, hours=hours)
        
        if gantt_chart_data:
            return jsonify({'success': True, 'gantt_chart_data': gantt_chart_data})
        else:
            return jsonify({'success': False, 'error': 'ガントチャートの生成に失敗しました'}), 500
            
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
