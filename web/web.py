from botocore.exceptions import ClientError
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from PIL import Image
import logging
import hashlib
import boto3
import redis
import io
import os

logging.basicConfig(level=logging.DEBUG)

cnc_channel = os.environ.get("SLACK_CHANNEL", "")

r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    db=int(os.environ.get("REDIS_DB", "0"))
)

s3_bucket = os.environ.get("AWS_S3_BUCKET", "")
s3_client = boto3.client('s3')
s3 = boto3.resource('s3')

app = App()
handler = SocketModeHandler(app)

def move_s3(src, dest):
    s3.Object(s3_bucket, dest).copy_from(CopySource=f"{s3_bucket}/{src}")
    s3.Object(s3_bucket, src).delete()

@app.action("disapprove")
def disapprove_cat(ack, body, client):
    url = body["message"]["blocks"][0]["accessory"]["image_url"]
    name = body["message"]["blocks"][0]["accessory"]["alt_text"]
    key = url.split("uploads/", 1)[1]
    src = f"uploads/{key}"
    dest = f"rejects/{key}"
    try:
        move_s3(src, dest)
    except:
        pass
    url = f"https://{s3_bucket}.s3.amazonaws.com/rejects/{key}"
    ack()
    client.chat_update(
        ts=body["message"]["ts"],
        channel=body["channel"]["id"],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Disapproved <{url}|{name}>"
                },
                "accessory": {
                    "type": "image",
                    "image_url": url,
                    "alt_text": "A bad cat"
                }
            }
        ]
    )

@app.action("approve")
def approve_cat(ack, body, client):
    url = body["message"]["blocks"][0]["accessory"]["image_url"]
    name = body["message"]["blocks"][0]["accessory"]["alt_text"]
    key = url.split("uploads/", 1)[1]
    src = f"uploads/{key}"
    dest = f"approved/{key}"
    move_s3(src, dest)
    url = f"https://{s3_bucket}.s3.amazonaws.com/approved/{key}"
    rkey = key.split(".", 1)[0]
    r.zadd("scores", {rkey: float(os.environ.get('START_SCORE', "1500"))})
    r.hset("urls", rkey, url)
    r.hset("names", rkey, name)
    ack()
    client.chat_update(
        ts=body["message"]["ts"],
        channel=body["channel"]["id"],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Approved <{url}|{name}>"
                },
                "accessory": {
                    "type": "image",
                    "image_url": url,
                    "alt_text": name
                }
            }
        ]
    )

from flask import Flask, render_template, request, jsonify

flask_app = Flask(__name__)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

@flask_app.route('/')
def root():
    return render_template('index.html')

@flask_app.route('/upload', methods=['POST'])
def upload():
    uploaded_file = request.files.get('file', None)
    name = request.form.get('name', None)
    if not name and uploaded_file:
        return "You must provide a name and file", 400
    image = Image.open(uploaded_file)
    image = image.convert('RGB')
    image_io = io.BytesIO()
    image.save(image_io, 'jpeg')
    image_io.seek(0)
    hash = hashlib.sha256()
    hash.update(image_io.read())
    object_name = f"uploads/{hash.hexdigest()}.jpg"
    image_io.seek(0)
    try:
        s3_client.upload_fileobj(
            image_io,
            s3_bucket,
            object_name,
            ExtraArgs={
                "Metadata": {
                    "catname": name,
                    "filename": uploaded_file.filename
                }
            }
        )
        url = f"https://{s3_bucket}.s3.amazonaws.com/{object_name}"
        app.client.chat_postMessage(
            channel=cnc_channel,
            text=f"Is {name} a good cat?",
            unfurl_links=False,
            unfurl_media=False,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Is \"<{url}|{name}>\" a good cat?"
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": url,
                        "alt_text": name
                    }
                },
                {
                    "block_id": "approve",
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Approve"
                            },
                            "value": "approve",
                            "style": "primary",
                            "action_id": "approve"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Delete"
                            },
                            "value": "disapprove",
                            "style": "danger",
                            "action_id": "disapprove"
                        }
                    ]
                }
            ]
        )
    except ClientError as e:
        logging.error(e)
        return "", 400
    return "", 200

handler.connect()

if __name__ == "__main__":
    app.start(3000)