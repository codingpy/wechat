import json
import math
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from enum import IntEnum

import qrcode
import requests
from requests_toolbelt import sessions
from requests_toolbelt.downloadutils import stream


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


class Base:
    @classmethod
    def from_dict(cls, d):
        kwargs = {}

        for key, value in d.items():
            key, value = preprocessor(key, value)

            kwargs[key] = value

        return cls(**kwargs)


def preprocessor(key, value):
    if key == "MemberList":
        value = list(map(Member.from_dict, value))

    key = to_snake(key)

    return key, value


def to_snake(s):
    return re.sub("(?<=[^_])((?=[A-Z][a-z])|(?<=[^A-Z])(?=[A-Z]))", "_", s).lower()


@dataclass
class UserBase(Base):
    user_name: str
    nick_name: str


@dataclass
class User(UserBase):
    uin: int
    head_img_url: str
    remark_name: str
    py_initial: str
    py_quan_pin: str
    remark_py_initial: str
    remark_py_quan_pin: str
    hide_input_bar_flag: int
    star_friend: int
    sex: int
    signature: str
    app_account_flag: int
    verify_flag: int
    contact_flag: int
    web_wx_plugin_switch: int
    head_img_flag: int
    sns_flag: int


@dataclass
class Member(UserBase):
    uin: int
    attr_status: int
    py_initial: str
    py_quan_pin: str
    remark_py_initial: str
    remark_py_quan_pin: str
    member_status: int
    display_name: str
    key_word: str


@dataclass
class Contact(UserBase):
    uin: int
    head_img_url: str
    contact_flag: int
    member_count: int
    member_list: list[Member]
    remark_name: str
    hide_input_bar_flag: int
    sex: int
    signature: str
    verify_flag: int
    owner_uin: int
    py_initial: str
    py_quan_pin: str
    remark_py_initial: str
    remark_py_quan_pin: str
    star_friend: int
    app_account_flag: int
    statues: int
    attr_status: int
    province: str
    city: str
    alias: str
    sns_flag: int
    uni_friend: int
    display_name: str
    chat_room_id: int
    key_word: str
    encry_chat_room_id: str
    is_owner: int

    @property
    def is_room(self):
        return self.user_name.startswith("@@")


class WeChatError(Exception):
    ...


def monkey_patch(r, *args, **kwargs):
    r.encoding = "utf-8"

    try:
        content = r.json()
    except requests.JSONDecodeError:
        return

    if "BaseResponse" in content:
        base_response = content["BaseResponse"]

        ret = base_response["Ret"]
        if ret != 0:
            raise WeChatError(ret, base_response["ErrMsg"])

    r.json = lambda: content


s = sessions.BaseUrlSession(base_url="https://wx2.qq.com")

s.hooks["response"] = monkey_patch

user = {}
contacts = {}
base_request = {}


def login():
    if "Uin" in base_request:
        uin = base_request["Uin"]

        r = s.get(f"/cgi-bin/mmwebwx-bin/webwxpushloginurl?uin={uin}")
        content = r.json()

        if content["ret"] == "0":
            uuid = content["uuid"]

            if check_login(uuid):
                return init()

    return login_qr()


def login_qr():
    r = s.get("https://login.wx.qq.com/jslogin?appid=wx782c26e4c19acffb")

    uuid = re.search('window.QRLogin.uuid = "(.*)"', r.text)[1]

    print_qr(f"https://login.weixin.qq.com/l/{uuid}")

    if check_login(uuid):
        return init()


def check_login(uuid):
    while True:
        r = s.get(f"https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login?uuid={uuid}")

        code = re.search("window.code=(\d+)", r.text)[1]

        if code == "200":
            redirect_uri = re.search('window.redirect_uri="(.*)"', r.text)[1]

            r = s.get(redirect_uri, allow_redirects=False)

            sid = re.search("<wxsid>(.*)</wxsid>", r.text)[1]
            uin = re.search("<wxuin>(.*)</wxuin>", r.text)[1]

            base_request.update({"Sid": sid, "Uin": int(uin)})

            return True

        if code == "400":
            return False


def init():
    r = s.post("/cgi-bin/mmwebwx-bin/webwxinit", json={"BaseRequest": {}})
    content = r.json()

    sync_key = content["SyncKey"]

    user.update(content["User"])

    add_contacts(content["ContactList"])

    add_contacts(
        batch_get_contacts(
            [{"UserName": user_name} for user_name in content["ChatSet"].split(",")]
        )
    )

    seq = 0

    while True:
        r = s.get(f"/cgi-bin/mmwebwx-bin/webwxgetcontact?seq={seq}")
        content = r.json()

        add_contacts(content["MemberList"])

        seq = content["Seq"]

        if seq == 0:
            break

    return check_msg(sync_key)


def batch_get_contacts(users):
    r = s.post(
        "/cgi-bin/mmwebwx-bin/webwxbatchgetcontact",
        json={"BaseRequest": {}, "Count": len(users), "List": users},
    )
    content = r.json()

    return content["ContactList"]


def check_msg(sync_key):
    sync_check_key = sync_key

    while True:
        try:
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
        except requests.ConnectionError:
            continue

        m = re.search('window.synccheck={retcode:"(.*)",selector:"(.*)"}', r.text)

        if m[1] != "0":
            logout()
            return

        msgs = []

        if m[2] != "0":
            r = s.post(
                "/cgi-bin/mmwebwx-bin/webwxsync",
                json={"BaseRequest": {}, "SyncKey": sync_key},
            )
            content = r.json()

            sync_check_key = content["SyncCheckKey"]
            sync_key = content["SyncKey"]

            add_contacts(content["ModContactList"])
            del_contacts(content["DelContactList"])

            msgs = content["AddMsgList"]

        yield msgs


def add_contacts(contacts):
    for contact in contacts:
        add_contact(contact)


def del_contacts(contacts):
    for contact in contacts:
        del_contact(contact)


def add_contact(contact):
    c = Contact.from_dict(contact)

    contacts[c.user_name] = c


def del_contact(contact):
    user_name = contact["UserName"]

    del contacts[user_name]


def logout():
    s.post("/cgi-bin/mmwebwx-bin/webwxlogout")


def print_qr(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.print_ascii()


def send(content, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendmsg",
        {"ToUserName": to_user_name, "Type": MsgType.TEXT, "Content": content},
    )


def send_img(media_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendmsgimg?fun=async&f=json",
        {"ToUserName": to_user_name, "Type": MsgType.IMAGE, "MediaId": media_id},
    )


def send_video(media_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendvideomsg?f=json",
        {"ToUserName": to_user_name, "Type": MsgType.VIDEO, "MediaId": media_id},
    )


def send_app(title, total_len, attach_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendappmsg",
        {
            "ToUserName": to_user_name,
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


def send_emoticon(media_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendemoticon?fun=sys",
        {"ToUserName": to_user_name, "Type": MsgType.EMOTICON, "MediaId": media_id},
    )


def post_msg(url, msg):
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

    return content["MsgID"]


def revoke(svr_msg_id, to_user_name):
    s.post(
        "/cgi-bin/mmwebwx-bin/webwxrevokemsg",
        json={
            "BaseRequest": {},
            "SvrMsgId": svr_msg_id,
            "ToUserName": to_user_name,
            "ClientMsgId": time.time_ns(),
        },
    )


def upload(path, to_user_name):
    client_media_id = time.time_ns()

    chunk_size = int(0.5 * 1024 * 1024)

    filename = os.path.basename(path)

    ctype, encoding = mimetypes.guess_type(path)
    if ctype is None or encoding is not None:
        # No guess could be made, or the file is encoded (compressed), so
        # use a generic bag-of-bits type.
        ctype = "application/octet-stream"

    maintype, subtype = ctype.split("/")
    if maintype == "image" and subtype != "gif":
        media_type = "pic"
    elif maintype == "video":
        media_type = "video"
    else:
        media_type = "doc"

    with open(path, "rb") as f:
        total_len = f.seek(0, os.SEEK_END)
        f.seek(0)

        upload_media_request = json.dumps(
            {
                "BaseRequest": base_request,
                "ClientMediaId": client_media_id,
                "TotalLen": total_len,
                "StartPos": 0,
                "DataLen": total_len,
                "MediaType": MediaType.ATTACHMENT,
                "ToUserName": to_user_name,
            }
        )

        chunks = math.ceil(total_len / chunk_size)

        for chunk in range(chunks):
            r = s.post(
                "https://file.wx2.qq.com/cgi-bin/mmwebwx-bin/webwxuploadmedia?f=json",
                files={"filename": (filename, f.read(chunk_size))},
                data={
                    "chunks": chunks,
                    "chunk": chunk,
                    "mediatype": media_type,
                    "uploadmediarequest": upload_media_request,
                },
            )

    content = r.json()

    return content["MediaId"]


def get_img(msg_id, path):
    download(f"/cgi-bin/mmwebwx-bin/webwxgetmsgimg?MsgID={msg_id}", path)


def get_voice(msg_id, path):
    download(f"/cgi-bin/mmwebwx-bin/webwxgetvoice?msgid={msg_id}", path)


def get_video(msg_id, path):
    download(
        f"/cgi-bin/mmwebwx-bin/webwxgetvideo?msgid={msg_id}",
        path,
        headers={"Range": "bytes=0-"},
    )


def get_media(media_id, path):
    filename = os.path.basename(path)

    download(
        f"https://file.wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetmedia?mediaid={media_id}&encryfilename={filename}",
        path,
    )


def download(url, path=None, **kwargs):
    r = s.get(url, stream=True, **kwargs)

    return stream.stream_response_to_file(r, path)
