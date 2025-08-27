from flask import Flask, request, abort
import os
import requests
from PIL import Image
import pytesseract
from io import BytesIO
from notion_client import Client

app = Flask(__name__)

# LINE & Notion API tokens
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

notion = Client(auth=NOTION_TOKEN)

def classify_category(text):
    if "커피" in text or "카페" in text:
        return "카페"
    elif "다이소" in text:
        return "생활"
    elif "배달" in text or "쿠팡" in text:
        return "식비"
    else:
        return "기타"

def create_notion_page(data):
    notion.pages.create(
        parent={"database_id": NOTION_DB_ID},
        properties={
            "날짜": {"title": [{"text": {"content": data.get("날짜")}}]},
            "시간": {"rich_text": [{"text": {"content": data.get("시간", "")}}]},
            "내역": {"rich_text": [{"text": {"content": data.get("내역")}}]},
            "메모": {"rich_text": [{"text": {"content": data.get("메모", "")}}]},
            "입출금구분": {"select": {"name": data.get("입출금구분")}},
            "은행": {"select": {"name": data.get("은행")}},
            "금액": {"number": data.get("금액")},
            "정산금액": {"number": data.get("정산금액")},
            "카테고리": {"select": {"name": data.get("카테고리")}},
        }
    )

@app.route("/line_webhook", methods=["POST"])
def line_webhook():
    payload = request.get_json()
    events = payload.get("events", [])

    for event in events:
        if event.get("type") == "message" and event["message"]["type"] == "image":
            message_id = event["message"]["id"]
            headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
            image_data = requests.get(f"https://api-data.line.me/v2/bot/message/{message_id}/content", headers=headers).content

            image = Image.open(BytesIO(image_data))
            text = pytesseract.image_to_string(image, lang="kor")

            lines = [line.strip() for line in text.split("\n") if line.strip()]
            for line in lines:
                if not line: continue
                try:
                    desc, amount = line.rsplit(" ", 1)
                    입출금 = "출금" if "-" in amount else "입금"
                    금액 = float(amount.replace("+", "").replace("-", "").replace(",", ""))
                    카테고리 = classify_category(desc)

                    data = {
                        "날짜": request.headers.get("X-Timestamp", "")[:10],
                        "시간": "",
                        "내역": desc,
                        "입출금구분": 입출금,
                        "은행": "신한은행",
                        "금액": -금액 if 입출금 == "출금" else 금액,
                        "정산금액": -금액 if 입출금 == "출금" else 금액,
                        "카테고리": 카테고리,
                        "메모": "",
                    }
                    create_notion_page(data)
                except Exception as e:
                    print("❌ OCR 파싱 실패:", line, "| 에러:", e)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
