#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ランプ色判定統合システム
画像から orange.png, green.png, red.png を切り出して色分析を実行
"""

import cv2
import numpy as np
import os
import glob
import time
import csv
import random
from datetime import datetime, timedelta
import requests
import json

# グローバル変数でフラグ管理
current_state = None  # None: 緑またはなし, True: オレンジ
orange_detection_start_time = None  # オレンジ検知開始時刻
notification_sent = False  # 通知済みフラグ
debug_mode = False  # デバッグモード（分→秒変換）

# 設定ファイルのグローバル変数
settings = None

# ========================================
# 設定ファイル管理機能
# ========================================

def load_settings():
    """setting.jsonから設定を読み込む"""
    global settings
    
    settings_file = "setting.json"
    
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            print(f"[SETTINGS] 設定ファイルを読み込みました: {settings_file}")
        else:
            print(f"[ERROR] 設定ファイルが見つかりません: {settings_file}")
            return False
    except Exception as e:
        print(f"[ERROR] 設定ファイルの読み込みに失敗しました: {e}")
        return False
    
    return True

def save_settings():
    """現在の設定をsetting.jsonに保存"""
    global settings
    
    settings_file = "setting.json"
    
    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        print(f"[SETTINGS] 設定ファイルを保存しました: {settings_file}")
        return True
    except Exception as e:
        print(f"[ERROR] 設定ファイルの保存に失敗しました: {e}")
        return False

def get_setting(key_path, default_value=None):
    """設定値を取得（ドット記法対応）"""
    global settings
    
    if settings is None:
        return default_value
    
    try:
        keys = key_path.split('.')
        value = settings
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        print(f"[WARNING] 設定キー '{key_path}' が見つかりません。デフォルト値を使用: {default_value}")
        return default_value

def update_setting(key_path, new_value):
    """設定値を更新"""
    global settings
    
    if settings is None:
        return False
    
    try:
        keys = key_path.split('.')
        current = settings
        for key in keys[:-1]:
            current = current[key]
        current[keys[-1]] = new_value
        return True
    except (KeyError, TypeError):
        print(f"[ERROR] 設定キー '{key_path}' の更新に失敗しました")
        return False

# ========================================
# 2.py からの関数（画像切り出し機能）
# ========================================

def get_image_files():
    """sample_imgフォルダから画像ファイルを取得"""
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join('sample_img', ext)))
        image_files.extend(glob.glob(os.path.join('sample_img', ext.upper())))
    
    # 切り出し済みファイルを除外
    excluded_files = get_setting('files.excluded_files', ['orange.png', 'green.png', 'cut.png'])
    filtered_files = []
    
    for file in image_files:
        filename = os.path.basename(file)
        if filename not in excluded_files:
            filtered_files.append(file)
    
    return sorted(filtered_files)

def get_random_image_path():
    """1.pngから4.pngまでをランダムで選択"""
    available_images = []
    
    # 設定から画像数とプレフィックスを取得
    image_count = get_setting('files.random_image_count', 4)
    prefix = get_setting('files.random_image_prefix', '')
    
    # 1.pngからN.pngまでの存在確認
    for i in range(1, image_count + 1):
        filename = f"{prefix}{i}.png" if prefix else f"{i}.png"
        image_path = os.path.join("sample_img", filename)
        if os.path.exists(image_path):
            available_images.append(image_path)
    
    if not available_images:
        print(f"[ERROR] sample_imgフォルダに1.png～{image_count}.pngが見つかりません")
        return None
    
    # ランダムに選択
    selected_image = random.choice(available_images)
    image_name = os.path.basename(selected_image)
    
    print(f"[RANDOM] ランダム選択画像: {image_name} ({len(available_images)}/{image_count}個利用可能)")
    return selected_image

def find_available_camera():
    """利用可能なカメラデバイスを検索"""
    print("[CAMERA] 利用可能なカメラを検索中...")
    
    # 設定から検索範囲を取得
    search_range = get_setting('camera.search_range', 5)
    
    for camera_index in range(search_range):
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print(f"[FOUND] カメラデバイス {camera_index} が利用可能です")
                return camera_index
    
    print("[ERROR] 利用可能なカメラデバイスが見つかりません")
    return None

def capture_from_camera():
    """カメラから画像をキャプチャして保存"""
    print("[CAMERA] カメラから画像をキャプチャ中...")
    
    # 利用可能なカメラを検索
    camera_index = find_available_camera()
    if camera_index is None:
        print("[ERROR] カメラにアクセスできません")
        print("USBカメラが接続されているか確認してください")
        print("利用可能なカメラデバイス:")
        print("  - /dev/video0 (通常の内蔵カメラ)")
        print("  - /dev/video1 (USB外部カメラ)")
        return None
    
    # カメラを初期化
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"[ERROR] カメラデバイス {camera_index} を開けませんでした")
        return None
    
    try:
        # フレームをキャプチャ
        ret, frame = cap.read()
        
        if not ret:
            print("[ERROR] フレームを取得できませんでした")
            return None
        
        # タイムスタンプ付きのファイル名で保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        capture_filename = f"camera_capture_{timestamp}.png"
        capture_path = os.path.join("sample_img", capture_filename)
        
        # 画像を保存
        if cv2.imwrite(capture_path, frame):
            print(f"[OK] カメラ画像を保存: {capture_path}")
            print(f"画像サイズ: {frame.shape[1]} x {frame.shape[0]}")
            return capture_path
        else:
            print("[ERROR] カメラ画像の保存に失敗しました")
            return None
            
    finally:
        cap.release()
        print("カメラを正常に閉じました")

def draw_text_with_background(image, text, position, font_scale=None, color=(255, 255, 255), bg_color=(0, 0, 0), thickness=None):
    """背景付きでテキストを描画"""
    if font_scale is None:
        font_scale = get_setting('display.font_scale_default', 0.35)
    if thickness is None:
        thickness = get_setting('display.font_thickness', 1)
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # テキストサイズを取得
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    
    # 背景矩形を描画
    x, y = position
    cv2.rectangle(image, (x - 5, y - text_height - 5), 
                 (x + text_width + 5, y + baseline + 5), bg_color, -1)
    
    # テキストを描画
    cv2.putText(image, text, position, font, font_scale, color, thickness)

def create_status_overlay(frame, detection_logs, current_time):
    """ステータス情報をオーバーレイで表示"""
    global current_state, orange_detection_start_time, notification_sent, debug_mode
    
    overlay_frame = frame.copy()
    y_offset = get_setting('display.y_offset_start', 25)
    line_height = get_setting('display.line_height', 20)
    
    # タイトル
    title_font_scale = get_setting('display.font_scale_title', 0.5)
    draw_text_with_background(overlay_frame, "LAMP DETECTION SYSTEM", (20, y_offset), 
                             font_scale=title_font_scale, color=(255, 255, 255), bg_color=(0, 100, 200))
    y_offset += line_height + 5
    
    # 現在時刻
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    draw_text_with_background(overlay_frame, f"TIME: {time_str}", (20, y_offset), 
                             color=(255, 255, 255), bg_color=(50, 50, 50))
    y_offset += line_height
    
    # デバッグモード表示
    mode_text = "[DEBUG MODE]" if debug_mode else "[NORMAL MODE]"
    mode_color = (0, 255, 255) if debug_mode else (255, 255, 255)
    mode_bg = (100, 0, 100) if debug_mode else (50, 50, 50)
    draw_text_with_background(overlay_frame, mode_text, (20, y_offset), 
                             color=mode_color, bg_color=mode_bg)
    y_offset += line_height + 5
    
    # 現在の検知状態
    if current_state == True:
        status_text = "[ORANGE DETECTED]"
        status_color = (0, 165, 255)  # オレンジ色
        status_bg = (0, 50, 100)
        
        if orange_detection_start_time:
            elapsed = time.time() - orange_detection_start_time.timestamp()
            time_unit = "s" if debug_mode else "min"
            display_time = elapsed if debug_mode else elapsed / 60
            duration_text = f"Duration: {display_time:.1f}{time_unit}"
            
            # 通知までの残り時間
            threshold_seconds = get_notification_threshold()
            remaining = max(0, threshold_seconds - elapsed)
            remaining_unit = "s" if debug_mode else "min"
            remaining_display = remaining if debug_mode else remaining / 60
            
            if remaining > 0:
                remaining_text = f"Alert in: {remaining_display:.1f}{remaining_unit}"
            else:
                remaining_text = "ALERT SENT" if notification_sent else "ALERT READY"
    else:
        status_text = "[GREEN/NONE DETECTED]"
        status_color = (0, 255, 0)  # 緑色
        status_bg = (0, 100, 0)
        duration_text = "Duration: --"
        remaining_text = "Alert: --"
    
    draw_text_with_background(overlay_frame, status_text, (20, y_offset), 
                             font_scale=0.5, color=status_color, bg_color=status_bg)
    y_offset += line_height
    
    draw_text_with_background(overlay_frame, duration_text, (20, y_offset), 
                             color=(255, 255, 255), bg_color=(50, 50, 50))
    y_offset += line_height
    
    draw_text_with_background(overlay_frame, remaining_text, (20, y_offset), 
                             color=(255, 255, 255), bg_color=(50, 50, 50))
    y_offset += line_height + 5
    
    # 検知ログの表示
    if detection_logs:
        logs_font_scale = get_setting('display.font_scale_logs', 0.3)
        recent_logs_count = get_setting('display.recent_logs_display', 5)
        
        draw_text_with_background(overlay_frame, "RECENT DETECTIONS:", (20, y_offset), 
                                 font_scale=logs_font_scale + 0.1, color=(255, 255, 255), bg_color=(100, 100, 0))
        y_offset += line_height
        
        recent_logs = detection_logs[-recent_logs_count:]  # 設定に応じた件数
        for log in recent_logs:
            log_color = (0, 165, 255) if "ORANGE" in log else (0, 255, 0)
            draw_text_with_background(overlay_frame, log, (30, y_offset), 
                                     font_scale=logs_font_scale, color=log_color, bg_color=(30, 30, 30))
            y_offset += 15
    
    # 操作説明
    y_offset += 5
    draw_text_with_background(overlay_frame, "Press ESC or 'q' to quit", (20, y_offset), 
                             font_scale=0.3, color=(255, 255, 255), bg_color=(100, 0, 0))
    
    return overlay_frame

def save_frame_for_web(frame):
    """Web表示用にフレームを画像ファイルとして保存"""
    try:
        # streamingディレクトリが存在しない場合は作成
        streaming_dir = "streaming"
        if not os.path.exists(streaming_dir):
            os.makedirs(streaming_dir)
        
        # 現在のフレームを保存
        current_frame_path = os.path.join(streaming_dir, "current_frame.jpg")
        success = cv2.imwrite(current_frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        if success:
            # タイムスタンプ付きでバックアップも保存（最新3枚のみ保持）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(streaming_dir, f"frame_{timestamp}.jpg")
            cv2.imwrite(backup_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # 古いバックアップファイルを削除（最新3枚のみ保持）
            cleanup_old_frames(streaming_dir)
        
    except Exception as e:
        print(f"[ERROR] Web用フレーム保存エラー: {e}")

def cleanup_old_frames(streaming_dir):
    """古いフレームファイルを削除"""
    try:
        import glob
        frame_files = glob.glob(os.path.join(streaming_dir, "frame_*.jpg"))
        frame_files.sort(reverse=True)  # 新しい順にソート
        
        # 最新3枚を残して削除
        for old_file in frame_files[3:]:
            try:
                os.remove(old_file)
            except:
                pass
    except Exception as e:
        print(f"[ERROR] フレームクリーンアップエラー: {e}")

def run_camera_with_live_display():
    """カメラ映像を常時表示しながら定期的に色検出を実行"""
    global current_state, orange_detection_start_time, notification_sent, debug_mode
    
    print("[CAMERA] ライブカメラモード開始")
    print("=" * 60)
    
    # 利用可能なカメラを検索
    camera_index = find_available_camera()
    if camera_index is None:
        print("[ERROR] カメラが利用できません")
        return False
    
    # カメラを初期化
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERROR] カメラデバイス {camera_index} を開けませんでした")
        return False
    
    # 初期状態をリセット
    current_state = None
    orange_detection_start_time = None
    notification_sent = False
    
    # CSVログファイルを初期化
    initialize_csv_log()
    
    # 検知間隔の設定
    if debug_mode:
        detection_interval = get_setting('detection.debug_detection_interval_seconds', 1)
    else:
        detection_interval = get_setting('detection.detection_interval_seconds', 60)
    last_detection_time = 0
    
    time_unit = get_time_unit()
    threshold_value = 10
    
    print(f"カメラ映像: 全画面リアルタイム表示")
    print(f"色検出間隔: {detection_interval}秒")
    print(f"[ORANGE] オレンジ{threshold_value}{time_unit}間連続検知で通知送信")
    if debug_mode:
        print("[WARNING] デバッグモード: 時間単位が秒に変更されています")
    print("ESCキーまたは'q'キーで終了")
    print("=" * 60)
    
    # 検知ログを保持
    detection_logs = []
    
    # ウィンドウを作成
    window_name = get_setting('display.window_title', 'Live Camera Feed - LAMP DETECTION')
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    # 全画面表示の設定
    if get_setting('display.fullscreen', True):
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    try:
        while True:
            # フレームをキャプチャ
            ret, frame = cap.read()
            if not ret:
                detection_logs.append(f"{datetime.now().strftime('%H:%M:%S')} - ERROR: Frame capture failed")
                break
            
            # 現在時刻
            current_time_unix = time.time()
            current_datetime = datetime.now()
            
            # 定期的に色検出を実行
            if current_time_unix - last_detection_time >= detection_interval:
                last_detection_time = current_time_unix
                
                # 現在のフレームを保存
                timestamp = current_datetime.strftime("%Y%m%d_%H%M%S")
                temp_filename = f"temp_frame_{timestamp}.png"
                temp_path = os.path.join("sample_img", temp_filename)
                
                if cv2.imwrite(temp_path, frame):
                    detection_logs.append(f"{current_datetime.strftime('%H:%M:%S')} - DETECTION: Processing...")
                    
                    # 色検出処理を実行（コンソール出力を抑制）
                    # process_single_analysis の代わりに直接処理
                    try:
                        if crop_and_save_all_colors(temp_path):
                            results = run_analysis_silent()  # 静音版の分析
                            if results and len(results) == 2:
                                judgment, confidence, reasons, scores = comprehensive_judgment(results)
                            
                                # 検知結果から割合を取得
                                orange_percentage = 0
                                green_percentage = 0
                                for result in results:
                                    if result['expected_color'] == 'オレンジ':
                                        orange_percentage = result['percentage']
                                    elif result['expected_color'] == '緑':
                                        green_percentage = result['percentage']
                                
                                # フラグ状態を更新
                                detection_state = update_detection_state(judgment, orange_percentage, green_percentage, os.path.basename(temp_path))
                                
                                # ログに記録
                                log_entry = f"{current_datetime.strftime('%H:%M:%S')} - {judgment} (O:{orange_percentage:.1f}% G:{green_percentage:.1f}%)"
                                detection_logs.append(log_entry)
                                
                                # ログが多すぎる場合は古いものを削除
                                if len(detection_logs) > 10:
                                    detection_logs = detection_logs[-10:]
                            else:
                                print("[WARNING] 色検出結果が不完全です")
                                detection_logs.append(f"{current_datetime.strftime('%H:%M:%S')} - ERROR: Detection failed")
                        else:
                            print("[WARNING] 画像切り出しに失敗しました")
                            detection_logs.append(f"{current_datetime.strftime('%H:%M:%S')} - ERROR: Crop failed")
                    
                    except Exception as detection_error:
                        print(f"[ERROR] 色検出処理でエラー: {detection_error}")
                        detection_logs.append(f"{current_datetime.strftime('%H:%M:%S')} - ERROR: {str(detection_error)}")
                    
                    # 一時ファイルを削除
                    try:
                        os.remove(temp_path)
                    except Exception as cleanup_error:
                        print(f"[WARNING] 一時ファイル削除エラー: {cleanup_error}")
            
            # ステータス情報をオーバーレイして表示
            try:
                display_frame = create_status_overlay(frame, detection_logs, current_time_unix)
                
                # 毎フレームWeb表示用に保存（軽量化のため5フレームに1回）
                if hasattr(run_camera_with_live_display, 'frame_counter'):
                    run_camera_with_live_display.frame_counter += 1
                else:
                    run_camera_with_live_display.frame_counter = 0
                
                if run_camera_with_live_display.frame_counter % 5 == 0:
                    try:
                        save_frame_for_web(display_frame)
                    except Exception as save_error:
                        print(f"[WARNING] フレーム保存エラー: {save_error}")
                        
            except Exception as overlay_error:
                print(f"[ERROR] オーバーレイ作成エラー: {overlay_error}")
                display_frame = frame  # オーバーレイ失敗時は元フレームを使用
            
            # 次回検知までの時間をオーバーレイ
            try:
                next_detection_in = detection_interval - (current_time_unix - last_detection_time)
                if next_detection_in > 0:
                    next_text = f"Next detection: {next_detection_in:.0f}s"
                    draw_text_with_background(display_frame, next_text, (20, frame.shape[0] - 30), 
                                            font_scale=0.4, color=(255, 255, 0), bg_color=(50, 50, 0))
                
                # 画像を表示
                cv2.imshow(window_name, display_frame)
                
            except Exception as display_error:
                print(f"[ERROR] 画面表示エラー: {display_error}")
                # エラー時は元フレームを表示
                cv2.imshow(window_name, frame)
            
            # キー入力をチェック
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):  # ESCキーまたは'q'キーで終了
                print("\n[EXIT] ユーザーによる終了要求")
                break
                
    except KeyboardInterrupt:
        print("\n[EXIT] キーボード割り込みで終了")
    except Exception as e:
        print(f"\n[ERROR] カメラループでエラーが発生: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[CAMERA] カメラとウィンドウを正常に閉じました")
        return True

def get_color_coordinates():
    """各色の座標範囲を定義"""
    orange_coords = get_setting('coordinates.orange', {'x1': 297, 'y1': 86, 'x2': 347, 'y2': 133})
    green_coords = get_setting('coordinates.green', {'x1': 303, 'y1': 110, 'x2': 350, 'y2': 164})
    
    color_coordinates = {
        'orange': (orange_coords['x1'], orange_coords['y1'], orange_coords['x2'], orange_coords['y2']),
        'green': (green_coords['x1'], green_coords['y1'], green_coords['x2'], green_coords['y2']),
    }
    return color_coordinates

def crop_and_save_all_colors(image_path):
    """すべての色座標で画像を切り出して保存"""
    print(f"\n画像切り出し処理を開始します...")
    print("=" * 50)
    
    # 画像を読み込み
    original_image = cv2.imread(image_path)
    if original_image is None:
        print("画像の読み込みに失敗しました")
        return False
    
    print(f"元画像: {os.path.basename(image_path)}")
    print(f"元画像サイズ: {original_image.shape[1]} x {original_image.shape[0]}")
    
    color_coordinates = get_color_coordinates()
    success_count = 0
    
    for color_name, coordinates in color_coordinates.items():
        x1, y1, x2, y2 = coordinates
        
        # 座標の妥当性をチェック
        height, width = original_image.shape[:2]
        x1 = max(0, min(x1, width))
        y1 = max(0, min(y1, height))
        x2 = max(0, min(x2, width))
        y2 = max(0, min(y2, height))
        
        if x1 >= x2 or y1 >= y2:
            print(f"⚠️ {color_name}の座標範囲が無効です")
            continue
        
        # 画像を切り出し
        cropped_image = original_image[y1:y2, x1:x2]
        
        # 保存
        extension = os.path.splitext(image_path)[1] or '.png'
        output_filename = f"{color_name}{extension}"
        output_path = os.path.join("sample_img", output_filename)
        
        if cv2.imwrite(output_path, cropped_image):
            print(f"✓ {color_name}: ({x1}, {y1}) → ({x2}, {y2}) | サイズ: {cropped_image.shape[1]}x{cropped_image.shape[0]}")
            success_count += 1
        else:
            print(f"❌ {color_name}の保存に失敗しました")
    
    print(f"\n切り出し完了: {success_count}/2 ファイル")
    return success_count == 2

# ========================================
# 3.py からの関数（色分析機能）
# ========================================

def load_image(image_path):
    """画像を読み込む"""
    if not os.path.exists(image_path):
        return None
    
    image = cv2.imread(image_path)
    if image is None:
        return None
    
    return image

def get_default_color_ranges():
    """デフォルトの色範囲設定を取得"""
    return {
        'オレンジ': [
            (np.array([11, 50, 50]), np.array([25, 255, 255]))      # オレンジ色
        ],
        '緑': [
            (np.array([40, 50, 50]), np.array([80, 255, 255]))      # 緑色
        ]
    }

def get_enhanced_color_ranges():
    """検出精度を向上させた色範囲設定"""
    return {
        'オレンジ': [
            # オレンジ色の範囲を拡張
            (np.array([8, 30, 30]), np.array([30, 255, 255]))       # オレンジ色（拡張）
        ],
        '緑': [
            # 緑色の範囲を拡張
            (np.array([35, 30, 30]), np.array([85, 255, 255]))      # 緑色（拡張）
        ]
    }

def get_strict_color_ranges():
    """誤検知を減らす厳格な色範囲設定"""
    return {
        'オレンジ': [
            # より狭い範囲で明度・彩度の下限を上げる
            (np.array([12, 80, 80]), np.array([25, 255, 255]))      # オレンジ色（厳格）
        ],
        '緑': [
            # より狭い範囲で明度・彩度の下限を上げる  
            (np.array([45, 80, 80]), np.array([75, 255, 255]))      # 緑色（厳格）
        ]
    }

def get_adaptive_color_ranges():
    """設定ファイルから動的に色範囲を取得"""
    # 設定ファイルから色範囲を取得（厳格モードを優先）
    color_mode = get_setting('detection.color_detection_mode', 'strict')
    
    if color_mode == 'strict':
        return get_strict_color_ranges()
    elif color_mode == 'enhanced':
        return get_enhanced_color_ranges()
    else:
        return get_default_color_ranges()

def create_custom_color_ranges(orange_ranges=None, green_ranges=None):
    """カスタム色範囲を作成"""
    custom_ranges = {}
    
    if orange_ranges:
        custom_ranges['オレンジ'] = orange_ranges
    if green_ranges:
        custom_ranges['緑'] = green_ranges
    
    # 指定されなかった色はデフォルト値を使用
    default_ranges = get_default_color_ranges()
    for color, ranges in default_ranges.items():
        if color not in custom_ranges:
            custom_ranges[color] = ranges
    
    return custom_ranges

def analyze_lamp_color(image, color_ranges=None, apply_preprocessing=True):
    """ランプの色を分析する（色範囲カスタマイズ対応）"""
    if image is None:
        return None
    
    # 前処理を適用（ノイズ除去と色の強調）
    if apply_preprocessing:
        image = preprocess_image_for_color_detection(image)
    
    # BGR から HSV 色空間に変換
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 色範囲が指定されていない場合は適応的範囲を使用
    if color_ranges is None:
        color_ranges = get_adaptive_color_ranges()
    
    color_pixels = {}
    
    for color_name, ranges in color_ranges.items():
        total_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        
        for lower, upper in ranges:
            mask = cv2.inRange(hsv, lower, upper)
            total_mask = cv2.bitwise_or(total_mask, mask)
        
        pixel_count = cv2.countNonZero(total_mask)
        color_pixels[color_name] = pixel_count
    
    return color_pixels

def preprocess_image_for_color_detection(image):
    """色検出のための前処理"""
    # ガウシアンブラーでノイズを除去
    blurred = cv2.GaussianBlur(image, (3, 3), 0)
    
    # 彩度を少し強調
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = cv2.multiply(hsv[:, :, 1], 1.2)  # 彩度を20%向上
    
    # HSVからBGRに戻す
    enhanced = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    return enhanced

def calibrate_color_detection(image_path):
    """色検出の校正を行う対話的な関数"""
    print("🎨 色検出校正ツール")
    print("=" * 50)
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 画像を読み込めませんでした: {image_path}")
        return None
    
    print(f"画像を読み込みました: {os.path.basename(image_path)}")
    print("画像サイズ:", image.shape[1], "x", image.shape[0])
    
    # デフォルト、拡張、厳格の3つのモードで比較
    modes = {
        "デフォルト": get_default_color_ranges(),
        "拡張版": get_enhanced_color_ranges(),
        "厳格版": get_strict_color_ranges()
    }
    
    print("\n📊 各モードでの検出結果:")
    print("-" * 50)
    
    best_mode = None
    best_total = 0
    
    for mode_name, color_ranges in modes.items():
        print(f"\n🔍 {mode_name}モード:")
        color_pixels = analyze_lamp_color(image, color_ranges)
        
        total_pixels = sum(color_pixels.values())
        
        for color, count in color_pixels.items():
            percentage = (count / total_pixels * 100) if total_pixels > 0 else 0
            print(f"  {color}: {count} ピクセル ({percentage:.1f}%)")
        
        print(f"  合計検出ピクセル: {total_pixels}")
        
        if total_pixels > best_total:
            best_total = total_pixels
            best_mode = mode_name
    
    print(f"\n🏆 推奨モード: {best_mode} (検出ピクセル数: {best_total})")
    
    # カスタム調整の提案
    print(f"\n⚙️ カスタム調整オプション:")
    print("1. デフォルト設定を使用")
    print("2. 拡張設定を使用")
    print("3. 厳格設定を使用（誤検知対策）")
    print("4. 手動で色範囲を調整")
    print("5. 視覚的に色範囲を確認")
    
    while True:
        try:
            choice = input("選択してください (1-5): ").strip()
            
            if choice == "1":
                return get_default_color_ranges()
            elif choice == "2":
                return get_enhanced_color_ranges()
            elif choice == "3":
                return get_strict_color_ranges()
            elif choice == "4":
                return manual_color_adjustment()
            elif choice == "5":
                visual_color_range_check(image, modes["厳格版"])
                continue
            else:
                print("無効な選択です。1-5の数字を入力してください。")
        except KeyboardInterrupt:
            print("\n校正を終了します")
            return get_strict_color_ranges()

def manual_color_adjustment():
    """手動で色範囲を調整"""
    print("\n🔧 手動色範囲調整")
    print("HSV値の範囲を設定してください")
    print("形式: H_min,S_min,V_min,H_max,S_max,V_max")
    print("例: 0,30,30,15,255,255")
    
    custom_ranges = {}
    
    colors = ['オレンジ', '緑']
    for color in colors:
        print(f"\n{color}の範囲を設定:")
        
        try:
            if color == 'オレンジ':
                range_input = input(f"範囲 (例: 8,30,30,30,255,255): ").strip()
            else:  # 緑
                range_input = input(f"範囲 (例: 35,30,30,85,255,255): ").strip()
            
            values = [int(x) for x in range_input.split(',')]
            
            custom_ranges[color] = [
                (np.array(values[:3]), np.array(values[3:]))
            ]
        except:
            print("無効な形式です。デフォルト値を使用します。")
            custom_ranges[color] = get_default_color_ranges()[color]
    
    return custom_ranges

def visual_color_range_check(image, color_ranges):
    """視覚的に色範囲を確認"""
    print("\n👁️ 視覚的色範囲確認")
    print("各色のマスクを表示します。ESCキーで次の色に進みます。")
    
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    for color_name, ranges in color_ranges.items():
        print(f"\n{color_name}の検出範囲を表示中...")
        
        total_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        
        for lower, upper in ranges:
            mask = cv2.inRange(hsv, lower, upper)
            total_mask = cv2.bitwise_or(total_mask, mask)
        
        # 元画像とマスクを表示
        result = cv2.bitwise_and(image, image, mask=total_mask)
        
        # ウィンドウサイズを調整
        cv2.namedWindow(f'{color_name} - 元画像', cv2.WINDOW_NORMAL)
        cv2.namedWindow(f'{color_name} - マスク', cv2.WINDOW_NORMAL)
        cv2.namedWindow(f'{color_name} - 検出結果', cv2.WINDOW_NORMAL)
        
        cv2.imshow(f'{color_name} - 元画像', image)
        cv2.imshow(f'{color_name} - マスク', total_mask)
        cv2.imshow(f'{color_name} - 検出結果', result)
        
        pixel_count = cv2.countNonZero(total_mask)
        print(f"{color_name}の検出ピクセル数: {pixel_count}")
        
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    print("視覚的確認が完了しました。")

def analyze_brightness(image):
    """画像の明度を分析"""
    if image is None:
        return False, 0
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    is_bright = mean_brightness > 100  # 閾値
    
    return is_bright, mean_brightness

def analyze_single_image(image_path, expected_color):
    """単一画像で期待される色の含有率を分析"""
    image = load_image(image_path)
    if image is None:
        return None
    
    # 色分析
    color_pixels = analyze_lamp_color(image)
    if not color_pixels:
        return None
    
    # 期待される色のピクセル数を取得
    expected_pixels = color_pixels.get(expected_color, 0)
    total_pixels = sum(color_pixels.values())
    
    if total_pixels > 0:
        percentage = (expected_pixels / total_pixels) * 100
    else:
        percentage = 0
    
    # 明度分析
    is_bright, brightness = analyze_brightness(image)
    
    result = {
        'file_name': os.path.basename(image_path),
        'expected_color': expected_color,
        'expected_pixels': expected_pixels,
        'total_color_pixels': total_pixels,
        'percentage': percentage,
        'is_bright': is_bright,
        'brightness': brightness,
        'all_colors': color_pixels
    }
    
    return result

def comprehensive_judgment(results):
    """総合的な判定を行う（誤検知対策強化版）"""
    if not results or len(results) != 2:
        return "判定不可", 0, ["分析結果が不完全です"]
    
    # 設定から動的に閾値を取得
    threshold = get_setting('detection.color_detection_threshold_percentage', 50.0)  # デフォルトを50%に上昇
    brightness_threshold = get_setting('detection.brightness_threshold_high', 100.0)  # 明度閾値も上昇
    minimum_pixel_count = get_setting('detection.minimum_pixel_count', 100)  # 最小ピクセル数
    
    # 各ファイルの結果を評価
    scores = {}
    
    for result in results:
        color = result['expected_color']
        percentage = result['percentage']
        brightness = result['brightness']
        expected_pixels = result['expected_pixels']
        total_pixels = result['total_color_pixels']
        
        # 複数条件での検証
        meets_percentage_threshold = percentage >= threshold
        meets_brightness_threshold = brightness >= brightness_threshold
        meets_pixel_threshold = expected_pixels >= minimum_pixel_count
        
        # スコア計算（より厳格な条件）
        score = 0
        if meets_percentage_threshold:
            score += percentage
        if meets_brightness_threshold:
            score += 15  # 明度ボーナス増加
        if meets_pixel_threshold:
            score += 10  # ピクセル数ボーナス
        
        # 総合判定条件
        all_conditions_met = (meets_percentage_threshold and 
                             meets_brightness_threshold and 
                             meets_pixel_threshold)
        
        scores[color] = {
            'score': score,
            'percentage': percentage,
            'brightness': brightness,
            'expected_pixels': expected_pixels,
            'total_pixels': total_pixels,
            'meets_percentage_threshold': meets_percentage_threshold,
            'meets_brightness_threshold': meets_brightness_threshold,
            'meets_pixel_threshold': meets_pixel_threshold,
            'all_conditions_met': all_conditions_met
        }
    
    # 全条件を満たす色があるかチェック
    valid_colors = [(color, data) for color, data in scores.items() if data['all_conditions_met']]
    
    if not valid_colors:
        # どの色も全条件を満たさない場合
        judgment = "不明"
        confidence = 0
        reasons = [
            f"すべての色が厳格な判定条件を満たしませんでした",
            f"必要条件: 含有率≥{threshold}%, 明度≥{brightness_threshold}, ピクセル数≥{minimum_pixel_count}"
        ]
        return judgment, confidence, reasons, scores
    
    # 最高スコアの色を判定（全条件を満たす色の中から）
    best_color = max(valid_colors, key=lambda x: x[1]['score'])
    color_name, color_data = best_color
    
    # 判定理由を生成
    reasons = []
    reasons.append(f"{color_name}が全ての判定条件を満たしました:")
    reasons.append(f"  含有率: {color_data['percentage']:.1f}% (閾値: {threshold}%)")
    reasons.append(f"  明度: {color_data['brightness']:.1f} (閾値: {brightness_threshold})")
    reasons.append(f"  検出ピクセル数: {color_data['expected_pixels']} (閾値: {minimum_pixel_count})")
    
    # 他の色の状況も報告
    other_colors = [c for c in scores.keys() if c != color_name]
    for other_color in other_colors:
        other_data = scores[other_color]
        if not other_data['all_conditions_met']:
            failed_conditions = []
            if not other_data['meets_percentage_threshold']:
                failed_conditions.append(f"含有率{other_data['percentage']:.1f}%")
            if not other_data['meets_brightness_threshold']:
                failed_conditions.append(f"明度{other_data['brightness']:.1f}")
            if not other_data['meets_pixel_threshold']:
                failed_conditions.append(f"ピクセル数{other_data['expected_pixels']}")
            reasons.append(f"{other_color}は条件不足: {', '.join(failed_conditions)}")
    
    # 最終判定
    judgment = color_name
    confidence = min(95, color_data['score'])  # 最大95%
    
    return judgment, confidence, reasons, scores

def get_time_unit():
    """デバッグモードに応じて時間単位を取得"""
    global debug_mode
    return "秒" if debug_mode else "分"

def get_notification_threshold():
    """デバッグモードに応じて通知閾値を取得（秒単位）"""
    global debug_mode
    if debug_mode:
        return get_setting('detection.debug_notification_threshold_seconds', 10)
    else:
        threshold_minutes = get_setting('detection.notification_threshold_minutes', 10)
        return threshold_minutes * 60

def get_time_delta(minutes=10):
    """デバッグモードに応じてtimedeltaを取得"""
    global debug_mode
    if debug_mode:
        return timedelta(seconds=minutes)  # デバッグモードでは分を秒として扱う
    else:
        return timedelta(minutes=minutes)

def format_time_remaining(remaining_seconds):
    """残り時間を適切な形式でフォーマット"""
    global debug_mode
    
    if debug_mode:
        return f"{int(remaining_seconds)}秒"
    else:
        remaining_minutes = remaining_seconds // 60
        remaining_sec = int(remaining_seconds % 60)
        return f"{int(remaining_minutes):02d}:{remaining_sec:02d}"

def send_notification(message):
    """通知を送信する関数（現在はコンソール出力）"""
    global debug_mode
    
    print("\n" + "!" * 60)
    print("!!! 重要な通知 !!!")
    if debug_mode:
        print("!!! [DEBUG MODE] !!!")
    print("!" * 60)
    print(f"MESSAGE: {message}")
    notify_teams(['to-murakami@akioka-ltd.jp', 'hide-inoue@akioka-ltd.jp'],'検査場からの通知','オレンジランプが10分間連続で点灯しています！')
    print(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if debug_mode:
        print("WARNING: デバッグモード - 10秒間連続検知")
    print("!" * 60)
    print()

def update_detection_state(judgment, orange_percentage=0, green_percentage=0, image_file=""):
    """検知状態を更新し、必要に応じて通知を送信"""
    global current_state, orange_detection_start_time, notification_sent, debug_mode
    
    current_time = datetime.now()
    time_unit = get_time_unit()
    threshold_seconds = get_notification_threshold()
    
    if judgment == "オレンジ":
        if current_state != True:
            # オレンジ検知開始
            current_state = True
            orange_detection_start_time = current_time
            notification_sent = False
            debug_info = " [デバッグモード]" if debug_mode else ""
            print(f"[ORANGE] オレンジ検知開始: {current_time.strftime('%H:%M:%S')}{debug_info}")
            
            # CSV記録: オレンジ検知開始
            log_to_csv("orange_start", judgment, orange_percentage, green_percentage, 0, image_file)
        else:
            # オレンジ継続検知中
            if orange_detection_start_time and not notification_sent:
                elapsed_time = current_time - orange_detection_start_time
                elapsed_seconds = elapsed_time.total_seconds()
                
                if elapsed_seconds >= threshold_seconds:
                    # 閾値時間連続でオレンジを検知
                    message = f"オレンジランプが10{time_unit}間連続で点灯しています！"
                    send_notification(message)
                    notification_sent = True
                    
                    # CSV記録: 通知送信
                    log_to_csv("notification", judgment, orange_percentage, green_percentage, elapsed_seconds, image_file)
                else:
                    # 残り時間を表示
                    remaining_seconds = threshold_seconds - elapsed_seconds
                    remaining_formatted = format_time_remaining(remaining_seconds)
                    print(f"[ORANGE] オレンジ継続中 - 通知まで残り: {remaining_formatted}")
                    
                    # CSV記録: オレンジ継続
                    log_to_csv("orange_continue", judgment, orange_percentage, green_percentage, elapsed_seconds, image_file)
    
    elif judgment == "緑":
        duration = 0
        if current_state == True and orange_detection_start_time:
            # オレンジから緑に変化 - 継続時間を計算
            elapsed_time = current_time - orange_detection_start_time
            duration = elapsed_time.total_seconds()
            
            # 継続時間を強調表示
            formatted_duration = format_duration_for_display(duration)
            print(f"[GREEN] 緑に変化 - オレンジ状態をリセット: {current_time.strftime('%H:%M:%S')}")
            print(f"[DURATION] オレンジ継続時間: {formatted_duration}")
            
            # CSV記録: オレンジ終了
            log_to_csv("orange_end", judgment, orange_percentage, green_percentage, duration, image_file)
            
            # 即座に継続時間分析を表示
            print(f"\n" + "="*25 + " 改善データ " + "="*25)
            analyze_orange_durations()
            print("="*60)
        else:
            # CSV記録: 緑検知
            log_to_csv("green_detection", judgment, orange_percentage, green_percentage, 0, image_file)
            
        current_state = None
        orange_detection_start_time = None
        notification_sent = False
        
    else:  # judgment == "不明" or その他
        duration = 0
        if current_state == True and orange_detection_start_time:
            # オレンジから不明に変化 - 継続時間を計算
            elapsed_time = current_time - orange_detection_start_time
            duration = elapsed_time.total_seconds()
            print(f"[UNKNOWN] 検知不明 - オレンジ状態をリセット: {current_time.strftime('%H:%M:%S')}")
            
            # CSV記録: オレンジ中断
            log_to_csv("orange_interrupted", judgment, orange_percentage, green_percentage, duration, image_file)
        else:
            # CSV記録: 不明検知
            log_to_csv("unknown_detection", judgment, orange_percentage, green_percentage, 0, image_file)
            
        current_state = None
        orange_detection_start_time = None
        notification_sent = False
    
    return current_state

def get_detection_status():
    """現在の検知状態を取得"""
    global current_state, orange_detection_start_time, notification_sent
    
    status = {
        'current_state': current_state,
        'orange_start_time': orange_detection_start_time,
        'notification_sent': notification_sent
    }
    
    if current_state == True and orange_detection_start_time:
        elapsed_time = datetime.now() - orange_detection_start_time
        elapsed_seconds = elapsed_time.total_seconds()
        threshold_seconds = get_notification_threshold()
        
        if debug_mode:
            status['elapsed_seconds'] = elapsed_seconds
            status['remaining_seconds'] = max(0, threshold_seconds - elapsed_seconds)
        else:
            status['elapsed_minutes'] = elapsed_seconds / 60
            status['remaining_minutes'] = max(0, (threshold_seconds - elapsed_seconds) / 60)
    
    return status

def initialize_csv_log():
    """CSVログファイルを初期化"""
    csv_file = "data.csv"
    
    # ファイルが存在しない場合はヘッダーを作成
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", 
                "event_type", 
                "detection_result", 
                "orange_percentage", 
                "green_percentage", 
                "duration_seconds", 
                "debug_mode",
                "image_file"
            ])
        print(f"[CSV] CSVログファイルを作成しました: {csv_file}")

def log_to_csv(event_type, detection_result, orange_percentage=0, green_percentage=0, duration_seconds=0, image_file=""):
    """検知イベントをCSVに記録"""
    global debug_mode
    
    csv_file = "data.csv"
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                event_type,
                detection_result,
                f"{orange_percentage:.1f}",
                f"{green_percentage:.1f}",
                f"{duration_seconds:.1f}",
                "debug" if debug_mode else "normal",
                image_file
            ])
        
        # オレンジから緑への切り替わり時間は特別に強調表示
        if event_type == "orange_end" and duration_seconds > 0:
            time_unit = "秒" if debug_mode else "分"
            display_duration = duration_seconds if debug_mode else duration_seconds / 60
            print(f"[IMPORTANT] オレンジ継続時間: {display_duration:.1f}{time_unit}")
            print(f"[CSV] 記録: {event_type} - {detection_result} (継続時間: {duration_seconds:.1f}秒, 画像: {image_file})")
        else:
            print(f"[CSV] 記録: {event_type} - {detection_result}")
    except Exception as e:
        print(f"❌ CSV記録エラー: {e}")

def analyze_orange_durations():
    """オレンジ継続時間の分析を実行"""
    csv_file = "data.csv"
    
    if not os.path.exists(csv_file):
        print("❌ data.csvファイルが見つかりません")
        return
    
    try:
        durations = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['event_type'] == 'orange_end' and float(row['duration_seconds']) > 0:
                    durations.append({
                        'timestamp': row['timestamp'],
                        'duration': float(row['duration_seconds']),
                        'mode': row['debug_mode']
                    })
        
        if not durations:
            print("📊 オレンジ継続時間のデータがまだありません")
            return
        
        # 統計情報を計算
        duration_values = [d['duration'] for d in durations]
        avg_duration = sum(duration_values) / len(duration_values)
        min_duration = min(duration_values)
        max_duration = max(duration_values)
        
        print(f"\n📊 オレンジ継続時間分析レポート")
        print("=" * 50)
        print(f"総記録数: {len(durations)}回")
        print(f"平均継続時間: {avg_duration:.1f}秒")
        print(f"最短継続時間: {min_duration:.1f}秒")
        print(f"最長継続時間: {max_duration:.1f}秒")
        
        # 最近の傾向を表示（最新5回）
        if len(durations) >= 2:
            recent_durations = durations[-5:]
            print(f"\n📈 最近の継続時間推移:")
            print("-" * 30)
            for i, d in enumerate(recent_durations, 1):
                mode_indicator = "🐛" if d['mode'] == 'debug' else "⏰"
                print(f"{i}. {d['timestamp']}: {d['duration']:.1f}秒 {mode_indicator}")
            
            # 改善傾向の分析
            if len(recent_durations) >= 2:
                first_duration = recent_durations[0]['duration']
                last_duration = recent_durations[-1]['duration']
                improvement = first_duration - last_duration
                
                print(f"\n📉 改善状況:")
                if improvement > 0:
                    print(f"✅ 改善中: {improvement:.1f}秒短縮")
                elif improvement < 0:
                    print(f"⚠️ 悪化: {abs(improvement):.1f}秒延長")
                else:
                    print(f"➡️ 横ばい")
        
    except Exception as e:
        print(f"❌ 分析エラー: {e}")

def format_duration_for_display(seconds):
    """継続時間を見やすい形式で表示"""
    global debug_mode
    
    if debug_mode:
        return f"{seconds:.1f}秒"
    else:
        if seconds < 60:
            return f"{seconds:.1f}秒"
        else:
            minutes = seconds / 60
            return f"{minutes:.1f}分 ({seconds:.1f}秒)"

def run_analysis():
    """分析を実行"""
    print(f"\n色分析処理を開始します...")
    print("=" * 50)
    
    # 分析対象ファイルと期待色の定義
    target_files = [
        ("green.png", "緑"),
        ("orange.png", "オレンジ")
    ]
    
    results = []
    
    # 各ファイルを分析
    for filename, expected_color in target_files:
        image_path = os.path.join("sample_img", filename)
        result = analyze_single_image(image_path, expected_color)
        if result:
            results.append(result)
            print(f"✓ {filename}: {expected_color} {result['percentage']:.1f}% (明度: {result['brightness']:.1f})")
        else:
            print(f"❌ {filename}の分析に失敗しました")
    
    return results

def run_analysis_silent():
    """分析を実行（コンソール出力を抑制）"""
    # 分析対象ファイルと期待色の定義
    target_files = [
        ("green.png", "緑"),
        ("orange.png", "オレンジ")
    ]
    
    results = []
    
    # 各ファイルを分析
    for filename, expected_color in target_files:
        image_path = os.path.join("sample_img", filename)
        result = analyze_single_image_silent(image_path, expected_color)
        if result:
            results.append(result)
    
    return results

def analyze_single_image_silent(image_path, expected_color):
    """単一画像で期待される色の含有率を分析（静音版）"""
    image = load_image(image_path)
    if image is None:
        return None
    
    # 色分析
    color_pixels = analyze_lamp_color(image)
    if not color_pixels:
        return None
    
    # 期待される色のピクセル数を取得
    expected_pixels = color_pixels.get(expected_color, 0)
    total_pixels = sum(color_pixels.values())
    
    if total_pixels > 0:
        percentage = (expected_pixels / total_pixels) * 100
    else:
        percentage = 0
    
    # 明度分析
    is_bright, brightness = analyze_brightness_silent(image)
    
    result = {
        'file_name': os.path.basename(image_path),
        'expected_color': expected_color,
        'expected_pixels': expected_pixels,
        'total_color_pixels': total_pixels,
        'percentage': percentage,
        'is_bright': is_bright,
        'brightness': brightness,
        'all_colors': color_pixels
    }
    
    return result

def analyze_brightness_silent(image):
    """画像の明度を分析（静音版）"""
    if image is None:
        return False, 0
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    is_bright = mean_brightness > 100  # 閾値
    
    return is_bright, mean_brightness

# ========================================
# メイン統合処理
# ========================================

def process_single_analysis(image_path, mode="固定ファイル"):
    """単一の分析処理を実行"""
    print(f"\n{'=' * 60}")
    print(f"🚦 ランプ色判定統合システム ({mode})")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("1. 画像から orange.png, green.png を切り出し")
    print("2. 各ファイルの色分析を実行")
    print("3. 総合判定結果を表示")
    print("=" * 60)
    
    # Step 1: 画像確認
    print(f"\n📁 Step 1: 画像確認 ({mode})")
    if image_path is None:
        print("❌ 画像ファイルが見つからないため処理をスキップします")
        return False
    
    # 使用画像ファイル名を取得
    image_filename = os.path.basename(image_path) if image_path else ""
    
    # Step 2: 切り出し処理
    print(f"\n✂️ Step 2: 画像切り出し")
    if not crop_and_save_all_colors(image_path):
        print("❌ 画像の切り出しに失敗しました")
        return False
    
    # Step 3: 色分析
    print(f"\n🔍 Step 3: 色分析")
    results = run_analysis()
    
    if not results:
        print("❌ 色分析に失敗しました")
        return False
    
    # Step 4: 総合判定
    print(f"\n🎯 Step 4: 総合判定")
    print("=" * 50)
    
    judgment, confidence, reasons, scores = comprehensive_judgment(results)
    
    # 詳細結果表示
    print("📊 各ファイルの分析結果:")
    print("-" * 30)
    for result in results:
        color = result['expected_color']
        score_data = scores[color]
        status = "🟢" if score_data['all_conditions_met'] else "🔴"
        
        print(f"{status} {result['file_name']}:")
        print(f"   期待色({color}): {result['percentage']:.1f}%")
        print(f"   明度: {result['brightness']:.1f}")
        print(f"   検出ピクセル数: {result['expected_pixels']}")
        print(f"   スコア: {score_data['score']:.1f}")
        print(f"   全条件クリア: {'✓' if score_data['all_conditions_met'] else '✗'}")
        print(f"   - 含有率条件: {'✓' if score_data['meets_percentage_threshold'] else '✗'}")
        print(f"   - 明度条件: {'✓' if score_data['meets_brightness_threshold'] else '✗'}")
        print(f"   - ピクセル数条件: {'✓' if score_data['meets_pixel_threshold'] else '✗'}")
        print()
    
    # 最終判定結果
    print("🏆 最終判定結果:")
    print("-" * 30)
    print(f"判定色: {judgment}")
    if judgment != "不明":
        print(f"信頼度: {confidence:.1f}%")
    
    print(f"\n📝 判定理由:")
    for i, reason in enumerate(reasons, 1):
        print(f"  {i}. {reason}")
    
    # サマリー
    print(f"\n📋 分析サマリー:")
    print("-" * 30)
    threshold = get_setting('detection.color_detection_threshold_percentage', 50.0)
    for result in results:
        status = "🟢" if result['percentage'] >= threshold else "🔴"
        print(f"{status} {result['file_name']}: {result['expected_color']} {result['percentage']:.1f}%")
    
    # 検知結果から割合を取得
    orange_percentage = 0
    green_percentage = 0
    
    for result in results:
        if result['expected_color'] == 'オレンジ':
            orange_percentage = result['percentage']
        elif result['expected_color'] == '緑':
            green_percentage = result['percentage']
    
    # フラグ状態を更新（画像ファイル名も渡す）
    detection_state = update_detection_state(judgment, orange_percentage, green_percentage, image_filename)
    
    # 検知状態の詳細情報を表示
    status_info = get_detection_status()
    print(f"\n🏷️ 検知状態情報:")
    print("-" * 30)
    print(f"現在の状態: {'🟠 オレンジ' if detection_state == True else '🟢 緑/なし'}")
    
    if detection_state == True:
        if debug_mode and status_info.get('elapsed_seconds') is not None:
            elapsed_sec = status_info['elapsed_seconds']
            remaining_sec = status_info.get('remaining_seconds', 0)
            print(f"オレンジ継続時間: {elapsed_sec:.1f}秒")
            if remaining_sec > 0:
                print(f"通知まで残り: {remaining_sec:.1f}秒")
            else:
                print(f"通知状態: {'送信済み' if status_info['notification_sent'] else '未送信'}")
        elif not debug_mode and status_info.get('elapsed_minutes') is not None:
            elapsed_min = status_info['elapsed_minutes']
            remaining_min = status_info.get('remaining_minutes', 0)
            print(f"オレンジ継続時間: {elapsed_min:.1f}分")
            if remaining_min > 0:
                print(f"通知まで残り: {remaining_min:.1f}分")
            else:
                print(f"通知状態: {'送信済み' if status_info['notification_sent'] else '未送信'}")
    
    print(f"\n✅ 処理完了!")
    return True

def run_fixed_file_mode():
    """ランダム画像ファイルモードで実行"""
    image_path = get_random_image_path()
    return process_single_analysis(image_path, "ランダム画像")

def run_target_file_mode():
    """target.pngファイルモードで実行"""
    target_path = os.path.join("sample_img", "target.png")
    
    if not os.path.exists(target_path):
        print(f"❌ {target_path} が見つかりません")
        print("sample_imgフォルダにtarget.pngファイルを配置してください")
        return False
    
    print(f"📁 対象ファイル: {target_path}")
    return process_single_analysis(target_path, "target.png")

def run_camera_mode():
    """カメラモードで実行"""
    image_path = capture_from_camera()
    return process_single_analysis(image_path, "カメラキャプチャ")

def run_loop_mode(mode="fixed", interval_minutes=10):
    """ループモードで定期実行"""
    global current_state, orange_detection_start_time, notification_sent, debug_mode
    
    time_unit = get_time_unit()
    threshold_value = 10
    
    # デバッグモードでは実行間隔も調整
    if debug_mode:
        actual_interval = interval_minutes * 60  # 分を秒に変換
        interval_display = f"{actual_interval:.0f}秒"
    else:
        actual_interval = interval_minutes
        interval_display = f"{interval_minutes}分"
    
    print(f"🔄 ループモード開始")
    print(f"実行モード: {'ランダム画像' if mode == 'fixed' else 'カメラ'}")
    print(f"実行間隔: {interval_display}")
    print(f"🟠 オレンジ{threshold_value}{time_unit}間連続検知で通知送信")
    if debug_mode:
        print("⚠️ デバッグモード: 時間単位が秒に変更されています")
    if mode == 'fixed':
        print("🎲 毎回1.png～4.pngからランダム選択")
    print("Ctrl+C で停止できます")
    print("=" * 60)
    
    # 初期状態をリセット
    current_state = None
    orange_detection_start_time = None
    notification_sent = False
    
    # CSVログファイルを初期化
    initialize_csv_log()
    
    execution_count = 0
    
    try:
        while True:
            execution_count += 1
            print(f"\n🔄 実行回数: {execution_count}")
            
            # 実行モードに応じて処理
            if mode == "fixed":
                success = run_fixed_file_mode()
            else:  # camera
                success = run_camera_mode()
            
            if success:
                print(f"✅ 実行 #{execution_count} 完了")
            else:
                print(f"❌ 実行 #{execution_count} 失敗")
            
            # 次回実行時刻を計算・表示
            if debug_mode:
                next_time = datetime.now() + timedelta(seconds=actual_interval)
                print(f"\n⏰ 次回実行予定: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"💤 {actual_interval:.0f}秒間待機中...")
                # 指定時間待機
                time.sleep(actual_interval)
            else:
                next_time = datetime.now() + timedelta(minutes=actual_interval)
                print(f"\n⏰ 次回実行予定: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"💤 {actual_interval}分間待機中...")
                # 指定時間待機
                time.sleep(actual_interval * 60)
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 ユーザーによる停止要求を受信")
        print(f"総実行回数: {execution_count}")
        print("プログラムを終了します")

def toggle_debug_mode():
    """デバッグモードの切り替え"""
    global debug_mode
    
    print("\n⚙️ デバッグモード設定")
    print("=" * 40)
    print(f"現在のモード: {'デバッグ (10秒)' if debug_mode else '通常 (10分)'}")
    print("デバッグモードでは10分→10秒に変更されます")
    
    choice = input("デバッグモードを有効にしますか？ (y/n): ").lower().strip()
    debug_mode = choice in ['y', 'yes']
    
    print(f"設定完了: {'デバッグモード' if debug_mode else '通常モード'}")
    return debug_mode

def display_menu():
    """メニューを表示"""
    global debug_mode
    
    print("\n[LAMP] ランプ色判定統合システム")
    print("=" * 60)
    print("実行モードを選択してください:")
    print("1. ランダム画像 (1.png-4.png) - 1回実行")
    print("2. カメラキャプチャ - 1回実行")
    print("3. target.png - 1回実行")
    interval_text = "1秒毎" if debug_mode else "1分毎"
    print(f"4. ランダム画像 - {interval_text}ループ実行")
    print(f"5. ライブカメラ - 映像表示+{interval_text}色検出")
    print("6. 色検出校正ツール (green/orange)")
    print("7. デバッグモード設定")
    print("8. オレンジ継続時間分析レポート")
    print("=" * 60)
    debug_indicator = "[DEBUG] デバッグ (10秒)" if debug_mode else "[NORMAL] 通常 (10分)"
    print(f"現在のモード: {debug_indicator}")

def select_mode():
    """実行モードを選択"""
    global debug_mode
    
    display_menu()
    
    while True:
        try:
            choice = input("選択してください (1-8): ").strip()
            
            if choice == "1":
                return "fixed_single"
            elif choice == "2":
                return "camera_single"
            elif choice == "3":
                return "target_single"
            elif choice == "4":
                return "fixed_loop"
            elif choice == "5":
                return "camera_loop"
            elif choice == "6":
                return "calibrate"
            elif choice == "7":
                toggle_debug_mode()
                display_menu()  # メニューを再表示
                continue
            elif choice == "8":
                analyze_orange_durations()
                input("\n何かキーを押すとメニューに戻ります...")
                display_menu()  # メニューを再表示
                continue
            else:
                print("無効な選択です。1-8の数字を入力してください。")
        except KeyboardInterrupt:
            print("\n終了します")
            return None

def notify_teams(mention_ids, title, message, url=None):
    print('Notifying Teams')
    webhook_url = 'https://1966akioka.webhook.office.com/webhookb2/24ce70d8-1691-4b5e-aa90-67e8f56b36de@2f4ef158-134f-4faa-8db9-ef94be3b003a/IncomingWebhook/06ec01534f77477f9679950d30ee326e/2300d87e-df72-43f2-9367-9269f638e309/V2IJW5BzNLuCXyS-1pxN-7C7Kz4wq_zOJuSow6OIc6hWU1'

    # メンションの生成
    if isinstance(mention_ids, str):
        mention_ids = [mention_ids]  # 単一のIDの場合はリストに変換

    mentions = [
        {
            "type": "mention",
            "text": f"<at>{id}</at>",
            "mentioned": {
                "id": id,
                "name": id
            }
        } for id in mention_ids
    ]

    # メンションテキストの生成
    mention_text = " ".join(f"@<at>{id}</at>" for id in mention_ids)

    # 基本のペイロード構造
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": mention_text,
                            "color": "attention",
                            "size": "large",
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": title,
                            "color": "default",
                            "size": "default",
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": message,
                            "color": "good",
                            "size": "medium",
                            "wrap": True
                        }
                    ],
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.0",
                    "msteams": {
                        "entities": mentions
                    }
                }
            }
        ]
    }

    # URLが指定されている場合、リンクを追加
    if url:
        payload["attachments"][0]["content"]["body"].append({
            "type": "TextBlock",
            "text": f"[在庫管理システム]({url})",
            "color": "accent",
            "size": "medium",
            "wrap": True
        })

    # Webhookに対してPOSTリクエストを送信
    response = requests.post(webhook_url, json=payload)

    # レスポンスの確認
    if response.status_code == 200:
        print("通知が送信されました！")
    else:
        print(f"通知の送信に失敗しました。ステータスコード: {response.status_code}")
        
def main():
    """メイン関数"""
    # 設定ファイルを読み込み
    if not load_settings():
        print("[ERROR] 設定ファイルの読み込みに失敗しました。プログラムを終了します。")
        return
    
    mode = select_mode()
    if mode is None:
        return
    
    print(f"\n選択されたモード: {mode}")
    print("=" * 60)
    
    if mode == "fixed_single":
        run_fixed_file_mode()
    elif mode == "camera_single":
        run_camera_mode()
    elif mode == "target_single":
        run_target_file_mode()
    elif mode == "fixed_loop":
        interval = 1/60 if debug_mode else 1  # デバッグモード: 1秒, 通常: 1分
        run_loop_mode("fixed", interval)
    elif mode == "camera_loop":
        run_camera_with_live_display()
    elif mode == "calibrate":
        # 校正モード
        image_path = get_random_image_path()
        if image_path:
            calibrate_color_detection(image_path)
        else:
            print("❌ 校正用画像が見つかりません")

if __name__ == "__main__":
    main()
