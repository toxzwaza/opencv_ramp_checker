import requests
import json

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

if __name__ == "__main__":
    # 使用例
    notify_teams(
        ['to-murakami@akioka-ltd.jp'],  # 複数のメンションが可能
        'テストタイトル',
        '送信完了！',
        url='https://example.com'  # URLはオプション
    )


# if __name__ == "__main__":
#     # チームに通知
#     notify_teams('to-murakami@akioka-ltd.jp', 'テストタイトル', '送信完了！”')