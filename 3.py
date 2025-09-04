import cv2
import numpy as np
import os

def load_image(image_path):
    """画像を読み込む"""
    if not os.path.exists(image_path):
        print(f"エラー: ファイルが見つかりません: {image_path}")
        return None
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"エラー: 画像を読み込めませんでした: {image_path}")
        return None
    
    print(f"画像を読み込みました: {image_path}")
    print(f"画像サイズ: {image.shape[1]} x {image.shape[0]}")
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
            # 赤色は HSV で 0-10 と 170-180 の範囲にある
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
    masks = {}
    
    for color_name, ranges in color_ranges.items():
        total_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        
        for lower, upper in ranges:
            mask = cv2.inRange(hsv, lower, upper)
            total_mask = cv2.bitwise_or(total_mask, mask)
        
        masks[color_name] = total_mask
        pixel_count = cv2.countNonZero(total_mask)
        color_pixels[color_name] = pixel_count
        
        print(f"{color_name}のピクセル数: {pixel_count}")
    
    return color_pixels, masks

def determine_lamp_color(color_pixels):
    """最も多いピクセル数の色を判定"""
    if not color_pixels or all(count == 0 for count in color_pixels.values()):
        return "不明", 0
    
    # 最大ピクセル数の色を取得
    dominant_color = max(color_pixels.items(), key=lambda x: x[1])
    color_name, pixel_count = dominant_color
    
    # 閾値チェック（ノイズを除去するため）
    min_threshold = 10  # 最小ピクセル数
    
    if pixel_count < min_threshold:
        return "不明", pixel_count
    
    return color_name, pixel_count

def analyze_brightness(image):
    """画像の明度を分析してランプが点灯しているかチェック"""
    if image is None:
        return False, 0
    
    # グレースケールに変換
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 平均明度を計算
    mean_brightness = np.mean(gray)
    
    # 最大明度を計算
    max_brightness = np.max(gray)
    
    print(f"平均明度: {mean_brightness:.2f}")
    print(f"最大明度: {max_brightness}")
    
    # 明度が一定以上なら点灯していると判定
    brightness_threshold = 100  # 調整可能な閾値
    is_bright = mean_brightness > brightness_threshold
    
    return is_bright, mean_brightness

def display_analysis(image, masks):
    """分析結果を視覚的に表示"""
    if image is None:
        return
    
    print("\n視覚的な分析結果を表示しますか？ (y/n): ", end="")
    choice = input().lower().strip()
    
    if choice == 'y' or choice == 'yes':
        # 元画像を表示
        cv2.namedWindow('Original Image', cv2.WINDOW_NORMAL)
        cv2.imshow('Original Image', image)
        
        # 各色のマスクを表示
        for color_name, mask in masks.items():
            if cv2.countNonZero(mask) > 0:  # ピクセルが存在する場合のみ表示
                cv2.namedWindow(f'{color_name} Mask', cv2.WINDOW_NORMAL)
                cv2.imshow(f'{color_name} Mask', mask)
                
                # マスクを適用した結果を表示
                result = cv2.bitwise_and(image, image, mask=mask)
                cv2.namedWindow(f'{color_name} Detection', cv2.WINDOW_NORMAL)
                cv2.imshow(f'{color_name} Detection', result)
        
        print("何かキーを押すと終了します...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def analyze_single_image(image_path, expected_color):
    """単一画像で期待される色の含有率を分析"""
    print(f"\n{expected_color}の分析中...")
    print("-" * 30)
    
    image = load_image(image_path)
    if image is None:
        return None
    
    # 色分析
    color_pixels, masks = analyze_lamp_color(image)
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
    
    print(f"期待色({expected_color})のピクセル数: {expected_pixels}")
    print(f"全色ピクセル数: {total_pixels}")
    print(f"期待色の割合: {percentage:.1f}%")
    print(f"明度: {brightness:.2f} ({'点灯' if is_bright else '消灯'})")
    
    return result

def comprehensive_judgment(results):
    """総合的な判定を行う"""
    if not results or len(results) != 3:
        return "判定不可", "分析結果が不完全です"
    
    print("\n" + "=" * 50)
    print("🔍 総合判定")
    print("=" * 50)
    
    # 各ファイルの結果を評価
    scores = {}
    threshold = 30.0  # 期待色の最小割合閾値（調整可能）
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
        
        print(f"{color}ファイル:")
        print(f"  期待色割合: {percentage:.1f}%")
        print(f"  明度: {brightness:.2f}")
        print(f"  スコア: {score:.1f}")
        print(f"  閾値クリア: {'✓' if percentage >= threshold else '✗'}")
        print()
    
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
    
    return judgment, confidence, reasons

def main():
    """メイン関数"""
    print("ランプ色総合判定ツール")
    print("=" * 50)
    print("green.png, orange.png, red.pngを分析して総合判定を行います")
    
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
        else:
            print(f"⚠️ {filename}の分析に失敗しました")
    
    # 総合判定
    if results:
        judgment, confidence, reasons = comprehensive_judgment(results)
        
        print("🎯 最終判定結果:")
        print("-" * 30)
        print(f"判定色: {judgment}")
        if judgment != "不明":
            print(f"信頼度: {confidence:.1f}%")
        print(f"\n判定理由:")
        for i, reason in enumerate(reasons, 1):
            print(f"  {i}. {reason}")
        
        # サマリー表示
        print(f"\n📋 分析サマリー:")
        print("-" * 30)
        for result in results:
            status = "🟢" if result['percentage'] >= 30 else "🔴"
            print(f"{status} {result['file_name']}: {result['expected_color']} {result['percentage']:.1f}%")
        
    else:
        print("❌ すべてのファイルの分析に失敗しました")

if __name__ == "__main__":
    main()
