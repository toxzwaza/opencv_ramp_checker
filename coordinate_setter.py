#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座標設定ツール
カメラ映像から各色ランプの座標を設定
"""

import cv2
import json
import os
import sys
import numpy as np
from datetime import datetime

# グローバル変数でマウス操作の状態を管理
drawing = False
start_point = (-1, -1)
end_point = (-1, -1)
current_color = "orange"  # 現在設定中の色
coordinates = {
    "orange": {"x1": 0, "y1": 0, "x2": 0, "y2": 0},
    "green": {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
}

def mouse_callback(event, x, y, flags, param):
    """マウスイベントを処理するコールバック関数"""
    global drawing, start_point, end_point, current_color, coordinates
    
    if event == cv2.EVENT_LBUTTONDOWN:
        # 左クリック開始
        drawing = True
        start_point = (x, y)
        end_point = (x, y)
        print(f"[{current_color.upper()}] ドラッグ開始: ({x}, {y})")
        
    elif event == cv2.EVENT_MOUSEMOVE:
        # マウス移動中
        if drawing:
            end_point = (x, y)
            
    elif event == cv2.EVENT_LBUTTONUP:
        # 左クリック終了
        drawing = False
        end_point = (x, y)
        
        # 座標を正規化（左上と右下を正しく設定）
        x1, y1 = min(start_point[0], end_point[0]), min(start_point[1], end_point[1])
        x2, y2 = max(start_point[0], end_point[0]), max(start_point[1], end_point[1])
        
        # 座標を保存
        coordinates[current_color] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        
        print(f"[{current_color.upper()}] 座標設定完了: ({x1}, {y1}) → ({x2}, {y2})")
        print(f"[{current_color.upper()}] サイズ: {x2-x1} x {y2-y1}")

def find_available_camera():
    """利用可能なカメラデバイスを検索"""
    print("[CAMERA] 利用可能なカメラを検索中...")
    
    for camera_index in range(5):
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print(f"[FOUND] カメラデバイス {camera_index} が利用可能です")
                return camera_index
    
    print("[ERROR] 利用可能なカメラデバイスが見つかりません")
    return None

def load_current_settings():
    """現在の設定を読み込み"""
    global coordinates
    
    try:
        if os.path.exists('setting.json'):
            with open('setting.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                coordinates["orange"] = settings.get("coordinates", {}).get("orange", {"x1": 0, "y1": 0, "x2": 0, "y2": 0})
                coordinates["green"] = settings.get("coordinates", {}).get("green", {"x1": 0, "y1": 0, "x2": 0, "y2": 0})
                print("[SETTINGS] 現在の設定を読み込みました")
                return True
    except Exception as e:
        print(f"[ERROR] 設定読み込みエラー: {e}")
    
    return False

def save_coordinates_to_settings():
    """座標をsetting.jsonに保存"""
    global coordinates
    
    try:
        # 現在の設定を読み込み
        settings = {}
        if os.path.exists('setting.json'):
            with open('setting.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
        
        # 座標を更新
        if "coordinates" not in settings:
            settings["coordinates"] = {}
        
        settings["coordinates"]["orange"] = coordinates["orange"]
        settings["coordinates"]["green"] = coordinates["green"]
        
        # ファイルに保存
        with open('setting.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        print("[SETTINGS] 座標設定を保存しました")
        return True
        
    except Exception as e:
        print(f"[ERROR] 座標保存エラー: {e}")
        return False

def draw_coordinate_overlay(frame):
    """座標設定用のオーバーレイを描画"""
    global drawing, start_point, end_point, current_color, coordinates
    
    overlay_frame = frame.copy()
    
    # 現在設定中の矩形を描画
    if drawing or (start_point != (-1, -1) and end_point != (-1, -1)):
        x1, y1 = min(start_point[0], end_point[0]), min(start_point[1], end_point[1])
        x2, y2 = max(start_point[0], end_point[0]), max(start_point[1], end_point[1])
        
        # 色を設定
        if current_color == "orange":
            color = (0, 165, 255)  # オレンジ (BGR)
        else:
            color = (0, 255, 0)    # 緑 (BGR)
        
        # 矩形を描画
        cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), color, 2)
        
        # 半透明の塗りつぶし
        if drawing:
            overlay = overlay_frame.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.addWeighted(overlay, 0.2, overlay_frame, 0.8, 0, overlay_frame)
    
    # 既に設定済みの座標を表示
    for color_name, coords in coordinates.items():
        if coords["x1"] != 0 or coords["y1"] != 0 or coords["x2"] != 0 or coords["y2"] != 0:
            x1, y1, x2, y2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]
            
            # 色を設定
            if color_name == "orange":
                display_color = (0, 165, 255)  # オレンジ
                text_color = (255, 255, 255)
            else:
                display_color = (0, 255, 0)    # 緑
                text_color = (0, 0, 0)
            
            # 設定済み座標を薄く表示
            if color_name != current_color:
                cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), display_color, 1)
                cv2.putText(overlay_frame, color_name.upper(), (x1, y1-5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, display_color, 2)
    
    # 操作説明を表示
    instructions = [
        f"現在設定中: {current_color.upper()}",
        "マウスドラッグで範囲を選択",
        "SPACEキー: 次の色に切り替え",
        "Sキー: 設定を保存",
        "ESCキー: 終了"
    ]
    
    y_offset = 30
    for i, instruction in enumerate(instructions):
        # 背景を描画
        (text_width, text_height), _ = cv2.getTextSize(instruction, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(overlay_frame, (10, y_offset - text_height - 5), 
                     (text_width + 20, y_offset + 5), (0, 0, 0), -1)
        
        # テキストを描画
        text_color = (0, 165, 255) if i == 0 else (255, 255, 255)
        cv2.putText(overlay_frame, instruction, (15, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
        y_offset += 35
    
    # 現在の座標情報を表示
    info_y = frame.shape[0] - 100
    coord_info = [
        f"Orange: ({coordinates['orange']['x1']}, {coordinates['orange']['y1']}) -> ({coordinates['orange']['x2']}, {coordinates['orange']['y2']})",
        f"Green:  ({coordinates['green']['x1']}, {coordinates['green']['y1']}) -> ({coordinates['green']['x2']}, {coordinates['green']['y2']})"
    ]
    
    for info in coord_info:
        (text_width, text_height), _ = cv2.getTextSize(info, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(overlay_frame, (10, info_y - text_height - 5), 
                     (text_width + 20, info_y + 5), (50, 50, 50), -1)
        cv2.putText(overlay_frame, info, (15, info_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 30
    
    return overlay_frame

def run_coordinate_setter():
    """座標設定ツールを実行"""
    global current_color, drawing, start_point, end_point
    
    print("=" * 60)
    print("📍 座標設定ツール")
    print("=" * 60)
    print("カメラ映像から各色ランプの座標を設定します")
    print("操作方法:")
    print("  - マウスドラッグ: 範囲選択")
    print("  - SPACEキー: 次の色に切り替え")
    print("  - Sキー: 設定を保存")
    print("  - ESCキー: 終了")
    print("=" * 60)
    
    # 現在の設定を読み込み
    load_current_settings()
    
    # カメラを検索
    camera_index = find_available_camera()
    if camera_index is None:
        print("[ERROR] カメラが見つかりません")
        return False
    
    # カメラを初期化
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERROR] カメラデバイス {camera_index} を開けませんでした")
        return False
    
    # ウィンドウを作成
    window_name = "Coordinate Setting Tool"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, mouse_callback)
    
    print(f"[CAMERA] カメラデバイス {camera_index} で座標設定を開始")
    print(f"[INFO] 最初に{current_color.upper()}の座標を設定してください")
    
    try:
        while True:
            # フレームをキャプチャ
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] フレームを取得できませんでした")
                break
            
            # オーバーレイを描画
            display_frame = draw_coordinate_overlay(frame)
            
            # 画像を表示
            cv2.imshow(window_name, display_frame)
            
            # キー入力をチェック
            key = cv2.waitKey(1) & 0xFF
            
            if key == 27:  # ESCキー
                print("[EXIT] 座標設定を終了します")
                break
            elif key == ord(' '):  # SPACEキー
                # 次の色に切り替え
                if current_color == "orange":
                    current_color = "green"
                    print(f"[INFO] {current_color.upper()}の座標設定に切り替えました")
                else:
                    current_color = "orange"
                    print(f"[INFO] {current_color.upper()}の座標設定に切り替えました")
                
                # 描画状態をリセット
                drawing = False
                start_point = (-1, -1)
                end_point = (-1, -1)
                
            elif key == ord('s') or key == ord('S'):  # Sキー
                # 設定を保存
                if save_coordinates_to_settings():
                    print("[SUCCESS] 座標設定を保存しました")
                    print("設定内容:")
                    for color, coords in coordinates.items():
                        print(f"  {color}: ({coords['x1']}, {coords['y1']}) → ({coords['x2']}, {coords['y2']})")
                    
                    # 確認メッセージ
                    print("\n設定を保存しました。Webアプリから監視システムを再起動してください。")
                    break
                else:
                    print("[ERROR] 座標設定の保存に失敗しました")
                    
    except KeyboardInterrupt:
        print("\n[EXIT] キーボード割り込みで終了")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[CAMERA] カメラを正常に閉じました")
        return True

def validate_coordinates():
    """座標の妥当性をチェック"""
    global coordinates
    
    errors = []
    
    for color, coords in coordinates.items():
        x1, y1, x2, y2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]
        
        if x1 >= x2 or y1 >= y2:
            errors.append(f"{color}の座標が無効です (x1 < x2, y1 < y2 である必要があります)")
        
        if x1 < 0 or y1 < 0 or x2 < 0 or y2 < 0:
            errors.append(f"{color}の座標に負の値があります")
        
        # 最小サイズチェック
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            errors.append(f"{color}の選択範囲が小さすぎます (最小10x10ピクセル)")
    
    return errors

def preview_coordinates():
    """設定した座標のプレビューを表示"""
    global coordinates
    
    print("\n" + "=" * 40)
    print("📍 座標設定プレビュー")
    print("=" * 40)
    
    for color, coords in coordinates.items():
        x1, y1, x2, y2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]
        width = x2 - x1
        height = y2 - y1
        
        color_indicator = "🟠" if color == "orange" else "🟢"
        print(f"{color_indicator} {color.upper()}:")
        print(f"   座標: ({x1}, {y1}) → ({x2}, {y2})")
        print(f"   サイズ: {width} x {height} ピクセル")
        print()

if __name__ == '__main__':
    # コマンドライン引数で直接実行された場合
    print("=" * 60)
    print("📍 座標設定ツール (スタンドアロン実行)")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        # プレビューモード
        load_current_settings()
        preview_coordinates()
    else:
        # 座標設定モード
        success = run_coordinate_setter()
        if success:
            # 設定内容を表示
            preview_coordinates()
            
            # バリデーション
            errors = validate_coordinates()
            if errors:
                print("⚠️ 警告:")
                for error in errors:
                    print(f"   - {error}")
            else:
                print("✅ 座標設定は正常です")
        
        print("\n座標設定ツールを終了します")
