import json
import math
import mimetypes
import os
import re
import time
from enum import IntEnum

import qrcode
import requests
from requests_toolbelt import sessions


class MsgType(IntEnum):
    TEXT = 1
    IMAGE = 3
    VOICE = 34
    VIDEO = 43
    EMOTICON = 47


class AppMsgType(IntEnum):
    ATTACH = 6


class MediaType(IntEnum):
    ATTACHMENT = 4


def utf_8(r, *args, **kwargs):
    r.encoding = "utf-8"


s = sessions.BaseUrlSession(base_url="https://wx2.qq.com")

s.hooks["response"] = utf_8

user = {}
contacts = {}
base_request = {}


def login():
    r = s.get("https://login.wx.qq.com/jslogin?appid=wx782c26e4c19acffb")

    uuid = re.search('window.QRLogin.uuid = "(.*)"', r.text)[1]

    print_qr(f"https://login.weixin.qq.com/l/{uuid}")

    redirect_uri = check_login(uuid)

    if redirect_uri:
        r = s.get(redirect_uri, allow_redirects=False)

        sid = re.search("<wxsid>(.*)</wxsid>", r.text)[1]
        uin = re.search("<wxuin>(.*)</wxuin>", r.text)[1]

        base_request.update({"Sid": sid, "Uin": int(uin)})


def print_qr(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.print_ascii()


def check_login(uuid):
    while True:
        r = s.get(f"https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login?uuid={uuid}")

        code = re.search("window.code=(\d+)", r.text)[1]

        if code == "200":
            return re.search('window.redirect_uri="(.*)"', r.text)[1]

        if code == "400":
            return


def init():
    r = s.post("/cgi-bin/mmwebwx-bin/webwxinit", json={"BaseRequest": {}})
    content = r.json()

    sync_key = content["SyncKey"]

    user.update(content["User"])

    add_contact(user)

    for contact in content["ContactList"]:
        add_contact(contact)

    chats = [{"UserName": user_name} for user_name in content["ChatSet"].split(",")]

    r = s.post(
        "/cgi-bin/mmwebwx-bin/webwxbatchgetcontact",
        json={"BaseRequest": {}, "Count": len(chats), "List": chats},
    )
    content = r.json()

    for contact in content["ContactList"]:
        add_contact(contact)

    r = s.get("/cgi-bin/mmwebwx-bin/webwxgetcontact")
    content = r.json()

    for contact in content["MemberList"]:
        add_contact(contact)

    return sync(sync_key)


def sync(sync_key):
    sync_check_key = sync_key

    while True:
        try:
            msgs = []

            r = s.get(
                "https://webpush.wx2.qq.com/cgi-bin/mmwebwx-bin/synccheck",
                params={
                    "sid": base_request["Sid"],
                    "uin": base_request["Uin"],
                    "synckey": "|".join(
                        f"{x['Key']}_{x['Val']}" for x in sync_check_key["List"]
                    ),
                },
            )

            m = re.search('window.synccheck={retcode:"(.*)",selector:"(.*)"}', r.text)

            if m[1] != "0":
                logout()
                return

            if m[2] != "0":
                r = s.post(
                    "/cgi-bin/mmwebwx-bin/webwxsync",
                    json={"BaseRequest": {}, "SyncKey": sync_key},
                )
                content = r.json()

                sync_check_key = content["SyncCheckKey"]
                sync_key = content["SyncKey"]

                for contact in content["ModContactList"]:
                    add_contact(contact)

                for contact in content["DelContactList"]:
                    del_contact(contact)

                msgs = content["AddMsgList"]

            yield msgs
        except requests.ConnectionError:
            pass


def add_contact(contact):
    contacts[contact["UserName"]] = contact


def del_contact(contact):
    del contacts[contact["UserName"]]


def logout():
    s.post("/cgi-bin/mmwebwx-bin/webwxlogout")


def send(content, to):
    return post(
        "/cgi-bin/mmwebwx-bin/webwxsendmsg",
        {"ToUserName": to, "Type": MsgType.TEXT, "Content": content},
    )


def send_img(media_id, to):
    return post(
        "/cgi-bin/mmwebwx-bin/webwxsendmsgimg?fun=async&f=json",
        {"ToUserName": to, "Type": MsgType.IMAGE, "MediaId": media_id},
    )


def send_video(media_id, to):
    return post(
        "/cgi-bin/mmwebwx-bin/webwxsendvideomsg?f=json",
        {"ToUserName": to, "Type": MsgType.VIDEO, "MediaId": media_id},
    )


def send_app(title, total_len, attach_id, to):
    return post(
        "/cgi-bin/mmwebwx-bin/webwxsendappmsg",
        {
            "ToUserName": to,
            "Type": AppMsgType.ATTACH,
            "Content": (
                f"<appmsg>"
                f"  <title>{title}</title>"
                f"  <type>{AppMsgType.ATTACH}</type>"
                f"  <appattach>"
                f"    <totallen>{total_len}</totallen>"
                f"    <attachid>{attach_id}</attachid>"
                f"  </appattach>"
                f"</appmsg>"
            ),
        },
    )


def send_emoticon(media_id, to):
    return post(
        "/cgi-bin/mmwebwx-bin/webwxsendemoticon?fun=sys",
        {"ToUserName": to, "Type": MsgType.EMOTICON, "MediaId": media_id},
    )


def post(url, msg):
    client_msg_id = time.time_ns()

    payload = {
        "BaseRequest": base_request,
        "Msg": {
            "ClientMsgId": client_msg_id,
            "LocalID": client_msg_id,
            "FromUserName": user["UserName"],
            **msg,
        },
    }

    r = s.post(url, data=json.dumps(payload, ensure_ascii=False).encode())
    content = r.json()

    if content["BaseResponse"]["Ret"] == 0:
        return content["MsgID"]


def revoke(svr_msg_id, to):
    r = s.post(
        "/cgi-bin/mmwebwx-bin/webwxrevokemsg",
        json={
            "BaseRequest": {},
            "SvrMsgId": svr_msg_id,
            "ToUserName": to,
            "ClientMsgId": time.time_ns(),
        },
    )
    content = r.json()

    return content["BaseResponse"]["Ret"]


def upload(file, to="filehelper"):
    client_media_id = time.time_ns()

    ctype, encoding = mimetypes.guess_type(file)

    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"

    maintype, subtype = ctype.split("/")

    if maintype == "image" and subtype != "gif":
        media_type = "pic"
    elif maintype == "video":
        media_type = "video"
    else:
        media_type = "doc"

    with open(file, "rb") as f:
        total_len = f.seek(0, os.SEEK_END)
        f.seek(0)

        chunk_size = int(0.5 * 1024 * 1024)

        chunks = math.ceil(total_len / chunk_size)

        for chunk in range(chunks):
            r = s.post(
                "https://file.wx2.qq.com/cgi-bin/mmwebwx-bin/webwxuploadmedia?f=json",
                files={"filename": f.read(chunk_size)},
                data={
                    "chunks": chunks,
                    "chunk": chunk,
                    "mediatype": media_type,
                    "uploadmediarequest": json.dumps(
                        {
                            "BaseRequest": base_request,
                            "ClientMediaId": client_media_id,
                            "TotalLen": total_len,
                            "StartPos": 0,
                            "DataLen": total_len,
                            "MediaType": MediaType.ATTACHMENT,
                            "ToUserName": to,
                        }
                    ),
                },
            )

    content = r.json()

    if content["BaseResponse"]["Ret"] == 0:
        return content["MediaId"]


def get_img(msg_id, out):
    download(f"/cgi-bin/mmwebwx-bin/webwxgetmsgimg?MsgID={msg_id}", out)


def get_voice(msg_id, out):
    download(f"/cgi-bin/mmwebwx-bin/webwxgetvoice?msgid={msg_id}", out)


def get_video(msg_id, out):
    download(
        f"/cgi-bin/mmwebwx-bin/webwxgetvideo?msgid={msg_id}",
        out,
        headers={"Range": "bytes=0-"},
    )


def get_media(media_id, out):
    filename = os.path.basename(out)

    download(
        f"https://file.wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetmedia?mediaid={media_id}&encryfilename={filename}",
        out,
    )


def download(url, out, **kwargs):
    r = s.get(url, stream=True, **kwargs)

    with open(out, "wb") as f:
        for chunk in r.iter_content(chunk_size=128):
            f.write(chunk)
