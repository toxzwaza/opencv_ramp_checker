from linebot import LineBotApi
from linebot.models import TextSendMessage

# LINE Developers で発行したチャネルアクセストークン
CHANNEL_ACCESS_TOKEN = "xi3FcCNyfb5BFmmWpgaxR6IXkHDzkHKYDzoNnP++7UZi+0hTH2hyfuEuu3YW44K2uxuDgbq2Qrgvm2J7DCiABbFVyPYRnZbwya3RKj0S0OopD+Z57DYaRKO3l/OozopQycjrw+r/1uPYA39PC8rXwwdB04t89/1O/w1cDnyilFU="

# グループID（GASで取得した値）
GROUP_ID = "C2ed9e7224aa74b7e27c06c0e0d8487e8"

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)

def notify_group(message: str):
    """
    LINEグループにテキストメッセージを送信する関数
    :param message: 送信するメッセージ（文字列）
    """
    try:
        line_bot_api.push_message(
            GROUP_ID,
            TextSendMessage(text=message)
        )
        print("✅ メッセージを送信しました")
    except Exception as e:
        print("❌ エラー:", e)

# 使い方
if __name__ == "__main__":
    notify_group("PythonからLINEグループに通知しています！")
