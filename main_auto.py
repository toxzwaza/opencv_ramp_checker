#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ランプ検知システム自動実行版
環境変数またはコマンドライン引数でモードを指定して自動実行
"""

import os
import sys

# main.pyから必要な関数をインポート
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import (
    load_settings, run_fixed_file_mode, run_camera_mode, 
    run_camera_with_live_display, run_loop_mode,
    calibrate_color_detection, get_random_image_path,
    analyze_orange_durations
)

def get_auto_mode():
    """自動実行モードを取得"""
    # 環境変数から取得
    auto_mode = os.environ.get('LAMP_AUTO_MODE')
    
    # コマンドライン引数から取得
    if len(sys.argv) > 1:
        auto_mode = sys.argv[1]
    
    return auto_mode

def main():
    """自動実行メイン関数"""
    print("[AUTO] ランプ検知システム自動実行版")
    print("=" * 60)
    
    # 設定ファイルを読み込み
    if not load_settings():
        print("[ERROR] 設定ファイルの読み込みに失敗しました。プログラムを終了します。")
        return
    
    # 自動実行モードを取得
    auto_mode = get_auto_mode()
    
    if not auto_mode:
        print("[ERROR] 自動実行モードが指定されていません")
        print("使用方法:")
        print("  python main_auto.py 1  # ランダム画像 - 1回実行")
        print("  python main_auto.py 2  # カメラキャプチャ - 1回実行")
        print("  python main_auto.py 3  # ランダム画像 - ループ実行")
        print("  python main_auto.py 4  # ライブカメラ - 映像表示+色検出")
        print("または環境変数 LAMP_AUTO_MODE を設定してください")
        return
    
    print(f"[AUTO] 自動実行モード: {auto_mode}")
    
    try:
        if auto_mode == "1":
            print("[AUTO] ランダム画像 - 1回実行")
            run_fixed_file_mode()
            
        elif auto_mode == "2":
            print("[AUTO] カメラキャプチャ - 1回実行")
            run_camera_mode()
            
        elif auto_mode == "3":
            print("[AUTO] ランダム画像 - ループ実行")
            # デバッグモードに応じて間隔を調整
            from main import debug_mode
            interval = 1/60 if debug_mode else 1
            run_loop_mode("fixed", interval)
            
        elif auto_mode == "4":
            print("[AUTO] ライブカメラ - 映像表示+色検出")
            run_camera_with_live_display()
            
        else:
            print(f"[ERROR] 無効な自動実行モード: {auto_mode}")
            print("有効なモード: 1, 2, 3, 4")
            return
            
    except KeyboardInterrupt:
        print("\n[AUTO] 自動実行を終了します")
    except Exception as e:
        print(f"[ERROR] 自動実行中にエラーが発生: {e}")
    finally:
        print("[AUTO] 自動実行完了")

if __name__ == '__main__':
    main()
