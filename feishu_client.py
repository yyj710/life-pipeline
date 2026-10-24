"""
飞书 API 客户端 - 封装常用操作
支持：消息发送、文档、日历、通讯录、审批
"""
import os
import json
from datetime import datetime
from typing import Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from lark_oapi.api.contact.v3 import *
from lark_oapi.api.calendar.v4 import *
from lark_oapi.api.docx.v1 import *
from lark_oapi.api.drive.v1 import *
from lark_oapi.api.bitable.v1 import *
from dotenv import load_dotenv

load_dotenv()


class FeishuClient:
    """飞书 API 客户端"""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")

        if not self.app_id or not self.app_secret:
            raise ValueError("请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")

        self.client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

    # ==================== 消息相关 ====================

    def send_text_message(self, receive_id: str, content: str) -> dict:
        """发送文本消息

        Args:
            receive_id: 接收者 ID（用户 open_id / chat_id 等）
            content: 消息内容（JSON 字符串格式）
        """
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("text")
                .content(json.dumps({"text": content}))
                .build()) \
            .build()

        response = self.client.im.v1.message.create(request)
        if response.success():
            return {"code": 0, "message_id": response.data.message_id}
        return {"code": response.code, "msg": response.msg, "error": response.error}

    def send_interactive_card(self, receive_id: str, card: dict) -> dict:
        """发送消息卡片（interactive 类型）

        Args:
            receive_id: 接收者 ID
            card: 消息卡片 JSON（飞书卡片模板）
        """
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("interactive")
                .content(json.dumps(card))
                .build()) \
            .build()

        response = self.client.im.v1.message.create(request)
        if response.success():
            return {"code": 0, "message_id": response.data.message_id}
        return {"code": response.code, "msg": response.msg, "error": response.error}

    # ==================== 通讯录相关 ====================

    def get_user_by_mobile(self, mobile: str) -> Optional[dict]:
        """根据手机号查询用户信息"""
        request = BatchGetIdUserRequest.builder() \
            .user_id_type("open_id") \
            .request_body(BatchGetIdUserRequestBody.builder()
                .mobiles([mobile])
                .build()) \
            .build()

        response = self.client.contact.v3.user.batch_get_id(request)
        if response.success() and response.data.user_list:
            user = response.data.user_list[0]
            return {"user_id": user.user_id, "open_id": user.open_id}
        return None

    def list_users(self, page_size: int = 50) -> list[dict]:
        """获取用户列表"""
        users = []
        page_token = ""

        while True:
            request = ListUserRequest.builder() \
                .user_id_type("open_id") \
                .page_size(page_size) \
                .page_token(page_token) \
                .build()

            response = self.client.contact.v3.user.list(request)
            if not response.success():
                break

            for item in response.data.items:
                users.append({
                    "open_id": item.open_id,
                    "name": item.name,
                    "email": item.email,
                    "mobile": item.mobile,
                })

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return users

    # ==================== 日历相关 ====================

    def list_calendars(self, page_size: int = 50) -> list[dict]:
        """获取当前用户的日历列表"""
        calendars = []
        page_token = ""

        while True:
            request = ListCalendarRequest.builder() \
                .page_size(page_size) \
                .page_token(page_token) \
                .build()

            response = self.client.calendar.v4.calendar.list(request)
            if not response.success():
                break

            for item in response.data.calendar_list:
                calendars.append({
                    "calendar_id": item.calendar.calendar_id,
                    "summary": item.calendar.summary,
                    "description": item.calendar.description,
                })

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return calendars

    def list_events(self, calendar_id: str, start_time: str = None, end_time: str = None) -> list[dict]:
        """获取日历日程

        Args:
            calendar_id: 日历 ID（primary 表示主日历）
            start_time: 开始时间 RFC3339 格式, 例 "2024-01-01T00:00:00+08:00"
            end_time: 结束时间
        """
        events = []
        page_token = ""

        while True:
            request = ListCalendarEventRequest.builder() \
                .calendar_id(calendar_id) \
                .page_size(50) \
                .page_token(page_token) \
                .start_time(start_time) \
                .end_time(end_time) \
                .build()

            response = self.client.calendar.v4.calendar_event.list(request)
            if not response.success():
                break

            for item in response.data.items:
                events.append({
                    "event_id": item.event_id,
                    "summary": item.summary,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                })

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return events

    def create_event(
        self,
        calendar_id: str,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
    ) -> dict:
        """创建日历日程"""
        import lark_oapi.api.calendar.v4 as cal_v4

        request = CreateCalendarEventRequest.builder() \
            .calendar_id(calendar_id) \
            .request_body(cal_v4.CalendarEvent.builder()
                .summary(summary)
                .description(description)
                .start_time(cal_v4.TimeInfo.builder()
                    .timestamp(start_time)
                    .build())
                .end_time(cal_v4.TimeInfo.builder()
                    .timestamp(end_time)
                    .build())
                .build()) \
            .build()

        response = self.client.calendar.v4.calendar_event.create(request)
        if response.success():
            return {"code": 0, "event_id": response.data.event_id}
        return {"code": response.code, "msg": response.msg}

    # ==================== 云文档相关 ====================

    def create_doc(self, title: str, folder_token: str = "") -> dict:
        """创建飞书文档"""
        request = CreateFileRequest.builder() \
            .request_body(CreateFileRequestBody.builder()
                .name(title)
                .type("docx")
                .folder_token(folder_token)
                .build()) \
            .build()

        response = self.client.drive.v1.file.create(request)
        if response.success():
            return {
                "code": 0,
                "token": response.data.file.token,
                "url": response.data.file.url,
            }
        return {"code": response.code, "msg": response.msg}

    def get_doc_content(self, document_id: str) -> dict:
        """读取飞书文档内容"""
        request = RawContentDocumentRequest.builder() \
            .document_id(document_id) \
            .build()

        response = self.client.docx.v1.document.raw_content(request)
        if response.success():
            return {"code": 0, "content": response.data.content}
        return {"code": response.code, "msg": response.msg}

    # ==================== 多维表格相关 ====================

    def list_base_tables(self, app_token: str) -> list[dict]:
        """列出多维表格中的所有数据表"""
        tables = []
        page_token = ""

        while True:
            request = ListAppTableRequest.builder() \
                .app_token(app_token) \
                .page_size(50) \
                .page_token(page_token) \
                .build()

            response = self.client.bitable.v1.app_table.list(request)
            if not response.success():
                break

            for item in response.data.items:
                tables.append({
                    "table_id": item.table_id,
                    "name": item.name,
                    "revision": item.revision,
                })

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return tables

    def list_table_fields(self, app_token: str, table_id: str) -> list[dict]:
        """列出数据表的字段结构"""
        fields = []
        page_token = ""

        while True:
            request = ListAppTableFieldRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(50) \
                .page_token(page_token) \
                .build()

            response = self.client.bitable.v1.app_table_field.list(request)
            if not response.success():
                break

            for item in response.data.items:
                fields.append({
                    "field_id": item.field_id,
                    "field_name": item.field_name,
                    "type": item.type,
                })

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return fields

    def list_records(
        self,
        app_token: str,
        table_id: str,
        page_size: int = 100,
        filter_str: str = "",
        sort_fields: list = None,
    ) -> list[dict]:
        """列出数据表记录

        Args:
            app_token: 多维表格 token
            table_id: 数据表 ID
            page_size: 每页数量
            filter_str: 筛选条件，如 "CurrentValue.[日期] > \"2026-06-01\""
            sort_fields: 排序字段列表
        """
        records = []
        page_token = ""

        while True:
            builder = ListAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(page_size) \
                .page_token(page_token)

            if filter_str:
                builder = builder.filter(filter_str)
            if sort_fields:
                builder = builder.sort(sort_fields)

            request = builder.build()
            response = self.client.bitable.v1.app_table_record.list(request)
            if not response.success():
                break

            for item in response.data.items:
                records.append({
                    "record_id": item.record_id,
                    "fields": item.fields,
                })

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return records

    def create_record(self, app_token: str, table_id: str, fields: dict) -> dict:
        """新增一条记录

        Args:
            app_token: 多维表格 token
            table_id: 数据表 ID
            fields: 字段键值对
        """
        request = CreateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .request_body(CreateAppTableRecordRequestBody.builder()
                .fields(fields)
                .build()) \
            .build()

        response = self.client.bitable.v1.app_table_record.create(request)
        if response.success():
            return {"code": 0, "record_id": response.data.record_id}
        return {"code": response.code, "msg": response.msg}

    def update_record(
        self, app_token: str, table_id: str, record_id: str, fields: dict
    ) -> dict:
        """更新一条记录

        Args:
            app_token: 多维表格 token
            table_id: 数据表 ID
            record_id: 记录 ID
            fields: 要更新的字段键值对
        """
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .record_id(record_id) \
            .request_body(UpdateAppTableRecordRequestBody.builder()
                .fields(fields)
                .build()) \
            .build()

        response = self.client.bitable.v1.app_table_record.update(request)
        if response.success():
            return {"code": 0, "record_id": response.data.record_id}
        return {"code": response.code, "msg": response.msg}

    def search_records(
        self,
        app_token: str,
        table_id: str,
        filter_str: str = "",
        search_keyword: str = "",
        page_size: int = 100,
        sort_fields: list = None,
    ) -> list[dict]:
        """搜索数据表记录（支持全文搜索和筛选）

        Args:
            app_token: 多维表格 token
            table_id: 数据表 ID
            filter_str: 筛选条件
            search_keyword: 全文搜索关键词
            page_size: 每页数量
            sort_fields: 排序字段列表
        """
        records = []
        page_token = ""

        while True:
            builder = SearchAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(page_size) \
                .page_token(page_token)

            body_builder = SearchAppTableRecordRequestBody.builder()
            if filter_str:
                body_builder = body_builder.filter(filter_str)
            if search_keyword:
                body_builder = body_builder.search_keyword(search_keyword)
            if sort_fields:
                body_builder = body_builder.sort(sort_fields)

            request = builder.request_body(body_builder.build()).build()
            response = self.client.bitable.v1.app_table_record.search(request)
            if not response.success():
                break

            for item in response.data.items:
                records.append({
                    "record_id": item.record_id,
                    "fields": item.fields,
                })

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return records

    # ==================== 审批相关 ====================

    def list_approvals(
        self,
        approval_code: str = "",
        start_time: int = None,
        end_time: int = None,
        page_size: int = 50,
    ) -> list[dict]:
        """获取审批实例列表

        Args:
            approval_code: 审批定义 code
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
        """
        approvals = []
        page_token = ""

        while True:
            request = lark.BaseRequest.builder() \
                .http_method("GET") \
                .uri("/open-apis/approval/v4/instances") \
                .headers({"Content-Type": "application/json"}) \
                .query_params({
                    "approval_code": approval_code,
                    "start_time": str(start_time) if start_time else "",
                    "end_time": str(end_time) if end_time else "",
                    "page_size": page_size,
                    "page_token": page_token,
                }) \
                .build()

            response = self.client.request(request)
            if response.code != 0:
                break

            data = json.loads(response.raw_body)
            approvals.extend(data.get("data", {}).get("instance_list", []))

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("page_token", "")

        return approvals


# ==================== 快速使用示例 ====================

if __name__ == "__main__":
    # 初始化客户端（需要先配置 .env 文件）
    client = FeishuClient()
    print(f"飞书客户端初始化成功 (App ID: {client.app_id[:8]}...)")
