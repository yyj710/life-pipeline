"""
示例：操作飞书审批
"""
import sys
sys.path.append("..")

from feishu_client import FeishuClient


def main():
    client = FeishuClient()

    # 获取审批实例列表
    # 需要先在飞书后台创建审批定义，获取 approval_code
    approval_code = "your_approval_code"  # 替换为实际的审批定义 code
    approvals = client.list_approvals(
        approval_code=approval_code,
        page_size=20,
    )

    print(f"审批列表 ({len(approvals)} 条):")
    for a in approvals:
        print(f"  - [{a.get('status')}] {a.get('instance_code')}")


if __name__ == "__main__":
    main()
