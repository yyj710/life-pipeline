"""
示例：操作飞书日历
"""
import sys
sys.path.append("..")

from feishu_client import FeishuClient


def main():
    client = FeishuClient()

    # 1. 获取日历列表
    calendars = client.list_calendars()
    print("日历列表:")
    for cal in calendars:
        print(f"  - {cal['summary']} ({cal['calendar_id']})")

    # 2. 获取主日历的日程
    if calendars:
        primary_cal = calendars[0]["calendar_id"]
        events = client.list_events(
            primary_cal,
            start_time="2026-06-02T00:00:00+08:00",
            end_time="2026-06-09T00:00:00+08:00",
        )
        print("\n本周日程:")
        for ev in events:
            print(f"  - {ev['summary']}")

    # 3. 创建日程
    # result = client.create_event(
    #     calendar_id="primary",
    #     summary="团队周会",
    #     start_time="2026-06-03T10:00:00+08:00",
    #     end_time="2026-06-03T11:00:00+08:00",
    #     description="每周团队同步会议",
    # )
    # print("创建日程:", result)


if __name__ == "__main__":
    main()
