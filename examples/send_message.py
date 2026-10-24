"""
示例：发送消息
"""
import sys
sys.path.append("..")

from feishu_client import FeishuClient


def main():
    client = FeishuClient()

    # 1. 发送文本消息到指定用户
    # receive_id 可以是 open_id、user_id、chat_id 或 email
    # 发送给个人请先获取用户的 open_id
    receive_id = "ou_xxxx"  # 替换为实际 open_id
    result = client.send_text_message(receive_id, "你好，这是一条来自飞书机器人的测试消息！")
    print("发送文本消息结果:", result)

    # 2. 发送消息卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"content": "📢 通知", "tag": "plain_text"},
            "template": "blue",
        },
        "elements": [
            {"tag": "div", "text": {"content": "这是一条卡片消息", "tag": "lark_md"}},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"content": "查看详情", "tag": "plain_text"},
                        "url": "https://open.feishu.cn",
                        "type": "default",
                    }
                ],
            },
        ],
    }
    result = client.send_interactive_card(receive_id, card)
    print("发送卡片消息结果:", result)


if __name__ == "__main__":
    main()
