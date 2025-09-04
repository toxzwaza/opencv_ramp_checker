import cv2
import sys
import os
import glob

# グローバル変数でマウス操作の状態を管理
drawing = False  # ドラッグ中かどうか
start_point = (-1, -1)  # ドラッグ開始点
end_point = (-1, -1)    # ドラッグ終了点
rectangle_drawn = False  # 矩形が描画されているかどうか

def mouse_callback(event, x, y, flags, param):
    """マウスイベントを処理するコールバック関数"""
    global drawing, start_point, end_point, rectangle_drawn
    
    if event == cv2.EVENT_LBUTTONDOWN:
        # 左クリック開始
        drawing = True
        start_point = (x, y)
        end_point = (x, y)
        rectangle_drawn = False
        print(f"ドラッグ開始: ({x}, {y})")
        
    elif event == cv2.EVENT_MOUSEMOVE:
        # マウス移動中
        if drawing:
            end_point = (x, y)
            
    elif event == cv2.EVENT_LBUTTONUP:
        # 左クリック終了
        drawing = False
        end_point = (x, y)
        rectangle_drawn = True
        print(f"ドラッグ終了: ({x}, {y})")
        print(f"矩形範囲: ({start_point[0]}, {start_point[1]}) から ({end_point[0]}, {end_point[1]})")

def reset_rectangle():
    """矩形描画をリセットする関数"""
    global rectangle_drawn, drawing, start_point, end_point
    rectangle_drawn = False
    drawing = False
    start_point = (-1, -1)
    end_point = (-1, -1)

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

def main():
    """画像ファイルから矩形描画を行うメイン関数"""
    
    # 画像ファイルを選択
    image_path = select_image_file()
    if image_path is None:
        print("画像ファイルが見つからないため終了します")
        sys.exit(1)
    
    # 画像を読み込み
    original_image = cv2.imread(image_path)
    if original_image is None:
        print(f"エラー: 画像ファイルを読み込めませんでした: {image_path}")
        sys.exit(1)
    
    print(f"画像を正常に読み込みました: {os.path.basename(image_path)}")
    print("ESCキーまたは'q'キーで終了します")
    print("マウスでドラッグして矩形を描画できます")
    print("'r'キーで矩形をリセットできます")
    
    # ウィンドウを作成してマウスコールバックを設定
    window_name = 'Image with Rectangle Drawing'
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback)
    
    try:
        while True:
            # 元画像をコピーして矩形を描画
            display_image = original_image.copy()
            
            # ドラッグ中または矩形が描画済みの場合、白い矩形を描画
            if drawing or rectangle_drawn:
                # 矩形の座標を正規化（左上と右下を正しく設定）
                x1, y1 = min(start_point[0], end_point[0]), min(start_point[1], end_point[1])
                x2, y2 = max(start_point[0], end_point[0]), max(start_point[1], end_point[1])
                
                # 白い矩形枠を描画（色：BGR形式で白は(255, 255, 255)、線の太さ：2）
                cv2.rectangle(display_image, (x1, y1), (x2, y2), (255, 255, 255), 2)
                
                # ドラッグ中の場合は半透明の矩形も表示
                if drawing:
                    overlay = display_image.copy()
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 255, 255), -1)
                    cv2.addWeighted(overlay, 0.1, display_image, 0.9, 0, display_image)
            
            # 画像を表示
            cv2.imshow(window_name, display_image)
            
            # キー入力をチェック
            key = cv2.waitKey(30) & 0xFF  # 静止画なので少し長めの待機時間
            
            # ESCキー (27) または 'q' キーで終了
            if key == 27 or key == ord('q'):
                print("終了します...")
                break
            # 'r' キーで矩形をリセット
            elif key == ord('r'):
                reset_rectangle()
                print("矩形をリセットしました")
                
    except KeyboardInterrupt:
        print("\nキーボード割り込みで終了します...")
    
    finally:
        # リソースを解放
        cv2.destroyAllWindows()
        print("ウィンドウを正常に閉じました")

if __name__ == "__main__":
    main()
