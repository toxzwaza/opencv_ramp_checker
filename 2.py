import cv2
import os
import glob
from datetime import datetime

def get_image_files():
    """sample_imgフォルダから画像ファイルを取得"""
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join('sample_img', ext)))
        image_files.extend(glob.glob(os.path.join('sample_img', ext.upper())))
    
    return sorted(image_files)

def select_image_file():
    """画像ファイルを選択する"""
    image_files = get_image_files()
    
    if not image_files:
        print("sample_imgフォルダに画像ファイルが見つかりません")
        print("対応形式: jpg, jpeg, png, bmp, tiff, tif")
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

def crop_image_by_color(image_path, color_name, coordinates):
    """指定された色の座標で画像を切り出す"""
    # 画像を読み込み
    image = cv2.imread(image_path)
    if image is None:
        print(f"エラー: 画像ファイルを読み込めませんでした: {image_path}")
        return None
    
    x1, y1, x2, y2 = coordinates
    
    # 座標の妥当性をチェック
    height, width = image.shape[:2]
    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))
    
    if x1 >= x2 or y1 >= y2:
        print(f"エラー: {color_name}の座標範囲が無効です")
        return None
    
    # 画像を切り出し
    cropped_image = image[y1:y2, x1:x2]
    print(f"{color_name}の切り出し範囲: ({x1}, {y1}) から ({x2}, {y2})")
    print(f"{color_name}の切り出し後サイズ: {cropped_image.shape[1]} x {cropped_image.shape[0]}")
    
    return cropped_image

def save_cropped_image_by_color(cropped_image, color_name, original_path):
    """色名付きで切り出した画像を保存"""
    if cropped_image is None:
        return None
    
    # 元のファイル名から拡張子を取得
    extension = os.path.splitext(original_path)[1]
    
    # シンプルな色名のファイル名を生成（拡張子がない場合は.pngを使用）
    if not extension:
        extension = '.png'
    
    output_filename = f"{color_name}{extension}"
    output_path = os.path.join("sample_img", output_filename)
    
    # 画像を保存（既存ファイルがあれば上書き）
    success = cv2.imwrite(output_path, cropped_image)
    
    if success:
        print(f"{color_name}の切り出し画像を保存しました: {output_path}")
        return output_path
    else:
        print(f"エラー: {color_name}の画像保存に失敗しました")
        return None

def process_all_colors(image_path):
    """すべての色座標で画像を切り出して保存"""
    print(f"元画像サイズを確認中...")
    original_image = cv2.imread(image_path)
    if original_image is None:
        print("画像の読み込みに失敗しました")
        return []
    
    print(f"元画像サイズ: {original_image.shape[1]} x {original_image.shape[0]}")
    
    color_coordinates = get_color_coordinates()
    saved_files = []
    
    print(f"\n3つの色座標で切り出し処理を開始します...")
    print("=" * 50)
    
    for color_name, coordinates in color_coordinates.items():
        print(f"\n{color_name.upper()}の処理中...")
        print("-" * 30)
        
        # 画像を切り出し
        cropped_image = crop_image_by_color(image_path, color_name, coordinates)
        
        if cropped_image is not None:
            # 色名付きで保存
            output_path = save_cropped_image_by_color(cropped_image, color_name, image_path)
            if output_path:
                saved_files.append((color_name, output_path))
        else:
            print(f"{color_name}の切り出しに失敗しました")
    
    return saved_files

def display_preview_all_colors(image_path, saved_files):
    """すべての色の切り出し結果をプレビュー表示"""
    original_image = cv2.imread(image_path)
    if original_image is None:
        return
    
    # 元画像に全ての矩形を描画
    display_original = original_image.copy()
    color_coordinates = get_color_coordinates()
    
    # 各色の矩形を異なる色で描画
    colors = {
        'orange': (0, 165, 255),    # オレンジ (BGR)
        'green': (0, 255, 0),       # 緑
        'red': (0, 0, 255)          # 赤
    }
    
    for color_name, coordinates in color_coordinates.items():
        x1, y1, x2, y2 = coordinates
        color = colors.get(color_name, (255, 255, 255))
        cv2.rectangle(display_original, (x1, y1), (x2, y2), color, 2)
        cv2.putText(display_original, color_name.upper(), (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    # 元画像を表示
    cv2.namedWindow('Original Image with All Crop Areas', cv2.WINDOW_NORMAL)
    cv2.imshow('Original Image with All Crop Areas', display_original)
    
    # 各色の切り出し画像を表示
    for color_name, file_path in saved_files:
        cropped_image = cv2.imread(file_path)
        if cropped_image is not None:
            window_name = f'{color_name.upper()} Cropped'
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.imshow(window_name, cropped_image)
    
    print("何かキーを押すと終了します...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def main():
    """メイン関数"""
    print("画像切り出しツール (マルチカラー対応)")
    print("=" * 50)
    print("orange、green、redの3つの座標範囲で画像を切り出します")
    print()
    
    # 現在の座標設定を表示
    color_coordinates = get_color_coordinates()
    print("現在の座標設定:")
    for color_name, coordinates in color_coordinates.items():
        x1, y1, x2, y2 = coordinates
        print(f"  {color_name}: ({x1}, {y1}) から ({x2}, {y2})")
    print()
    
    # 画像ファイルを選択
    image_path = select_image_file()
    if image_path is None:
        print("画像ファイルが見つからないため終了します")
        return
    
    # すべての色座標で処理
    saved_files = process_all_colors(image_path)
    
    if saved_files:
        print("\n" + "=" * 50)
        print("処理が完了しました！")
        print(f"保存されたファイル数: {len(saved_files)}")
        print("-" * 30)
        
        for color_name, file_path in saved_files:
            print(f"  {color_name}: {os.path.basename(file_path)}")
        
        # プレビュー表示の選択
        show_preview = input("\n切り出し結果をプレビューしますか？ (y/n): ").lower().strip()
        if show_preview == 'y' or show_preview == 'yes':
            display_preview_all_colors(image_path, saved_files)
    else:
        print("すべての画像の切り出しに失敗しました")

if __name__ == "__main__":
    main()
