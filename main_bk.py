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
from datetime import datetime

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
    excluded_files = ['orange.png', 'green.png', 'red.png', 'cut.png']
    filtered_files = []
    
    for file in image_files:
        filename = os.path.basename(file)
        if filename not in excluded_files:
            filtered_files.append(file)
    
    return sorted(filtered_files)

def select_image_file():
    """画像ファイルを選択する"""
    image_files = get_image_files()
    
    if not image_files:
        print("sample_imgフォルダに分析対象の画像ファイルが見つかりません")
        print("対応形式: jpg, jpeg, png, bmp, tiff, tif")
        print("注意: orange.png, green.png, red.png, cut.pngは除外されます")
        return None
    
    if len(image_files) == 1:
        print(f"画像ファイルを読み込みます: {image_files[0]}")
        return image_files[0]
    
    print("複数の画像ファイルが見つかりました:")
    for i, file in enumerate(image_files):
        print(f"{i + 1}: {os.path.basename(file)}")
    
    while True:
        try:
            choice = input("画像を選択してください (番号を入力): ")
            index = int(choice) - 1
            if 0 <= index < len(image_files):
                print(f"選択された画像: {image_files[index]}")
                return image_files[index]
            else:
                print("無効な番号です。再入力してください。")
        except (ValueError, KeyboardInterrupt):
            print("無効な入力です。再入力してください。")

def get_color_coordinates():
    """各色の座標範囲を定義"""
    color_coordinates = {
        'orange': (297, 86, 347, 133),  # (x1, y1, x2, y2)
        'green': (303, 110, 350, 164),  # greenの座標範囲
        'red': (299, 168, 348, 213)     # redの座標範囲
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
    
    print(f"\n切り出し完了: {success_count}/3 ファイル")
    return success_count == 3

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

def analyze_lamp_color(image):
    """ランプの色を分析する"""
    if image is None:
        return None
    
    # BGR から HSV 色空間に変換
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 色の範囲を定義 (HSV)
    color_ranges = {
        '赤': [
            (np.array([0, 50, 50]), np.array([10, 255, 255])),      # 赤色下限
            (np.array([170, 50, 50]), np.array([180, 255, 255]))    # 赤色上限
        ],
        'オレンジ': [
            (np.array([11, 50, 50]), np.array([25, 255, 255]))      # オレンジ色
        ],
        '緑': [
            (np.array([40, 50, 50]), np.array([80, 255, 255]))      # 緑色
        ]
    }
    
    color_pixels = {}
    
    for color_name, ranges in color_ranges.items():
        total_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        
        for lower, upper in ranges:
            mask = cv2.inRange(hsv, lower, upper)
            total_mask = cv2.bitwise_or(total_mask, mask)
        
        pixel_count = cv2.countNonZero(total_mask)
        color_pixels[color_name] = pixel_count
    
    return color_pixels

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
    """総合的な判定を行う"""
    if not results or len(results) != 3:
        return "判定不可", 0, ["分析結果が不完全です"]
    
    # 各ファイルの結果を評価
    scores = {}
    threshold = 30.0  # 期待色の最小割合閾値
    brightness_threshold = 80.0  # 明度閾値
    
    for result in results:
        color = result['expected_color']
        percentage = result['percentage']
        brightness = result['brightness']
        
        # スコア計算（期待色割合 + 明度ボーナス）
        score = percentage
        if brightness > brightness_threshold:
            score += 10  # 明度ボーナス
        
        scores[color] = {
            'score': score,
            'percentage': percentage,
            'brightness': brightness,
            'meets_threshold': percentage >= threshold
        }
    
    # 最高スコアの色を判定
    best_color = max(scores.items(), key=lambda x: x[1]['score'])
    color_name, color_data = best_color
    
    # 判定理由を生成
    reasons = []
    
    if color_data['meets_threshold']:
        reasons.append(f"{color_name}の含有率が{color_data['percentage']:.1f}%で閾値({threshold}%)を超過")
    
    if color_data['brightness'] > brightness_threshold:
        reasons.append(f"十分な明度({color_data['brightness']:.1f})を検出")
    
    # 他の色との比較
    other_colors = [c for c in scores.keys() if c != color_name]
    for other_color in other_colors:
        if scores[other_color]['percentage'] < threshold:
            reasons.append(f"{other_color}は含有率{scores[other_color]['percentage']:.1f}%で閾値未満")
    
    # 最終判定
    if color_data['meets_threshold']:
        judgment = color_name
        confidence = min(95, color_data['score'])  # 最大95%
    else:
        judgment = "不明"
        confidence = 0
        reasons = ["すべての色が閾値を下回りました"]
    
    return judgment, confidence, reasons, scores

def run_analysis():
    """分析を実行"""
    print(f"\n色分析処理を開始します...")
    print("=" * 50)
    
    # 分析対象ファイルと期待色の定義
    target_files = [
        ("green.png", "緑"),
        ("orange.png", "オレンジ"),
        ("red.png", "赤")
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

# ========================================
# メイン統合処理
# ========================================

def main():
    """メイン関数"""
    print("🚦 ランプ色判定統合システム")
    print("=" * 60)
    print("1. 画像から orange.png, green.png, red.png を切り出し")
    print("2. 各ファイルの色分析を実行")
    print("3. 総合判定結果を表示")
    print("=" * 60)
    
    # Step 1: 画像選択と切り出し
    print("\n📁 Step 1: 画像選択")
    image_path = select_image_file()
    if image_path is None:
        print("❌ 画像ファイルが見つからないため終了します")
        return
    
    # Step 2: 切り出し処理
    print(f"\n✂️ Step 2: 画像切り出し")
    if not crop_and_save_all_colors(image_path):
        print("❌ 画像の切り出しに失敗しました")
        return
    
    # Step 3: 色分析
    print(f"\n🔍 Step 3: 色分析")
    results = run_analysis()
    
    if not results:
        print("❌ 色分析に失敗しました")
        return
    
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
        status = "🟢" if score_data['meets_threshold'] else "🔴"
        
        print(f"{status} {result['file_name']}:")
        print(f"   期待色({color}): {result['percentage']:.1f}%")
        print(f"   明度: {result['brightness']:.1f}")
        print(f"   スコア: {score_data['score']:.1f}")
        print(f"   閾値クリア: {'✓' if score_data['meets_threshold'] else '✗'}")
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
    for result in results:
        status = "🟢" if result['percentage'] >= 30 else "🔴"
        print(f"{status} {result['file_name']}: {result['expected_color']} {result['percentage']:.1f}%")
    
    print(f"\n✅ 処理完了!")

if __name__ == "__main__":
    main()
