"""
示例：操作飞书文档
"""
import sys
sys.path.append("..")

from feishu_client import FeishuClient


def main():
    client = FeishuClient()

    # 1. 创建文档
    result = client.create_doc("测试文档 - Python API 创建")
    print("创建文档:", result)
    doc_token = result.get("token")

    # 2. 读取文档内容
    if doc_token:
        result = client.get_doc_content(doc_token)
        print("文档内容:", result)


if __name__ == "__main__":
    main()
