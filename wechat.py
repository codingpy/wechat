import json
import math
import mimetypes
import os
import re
import time
import typing
from dataclasses import dataclass, field, fields
from enum import IntEnum, IntFlag
from http.client import BadStatusLine
from xml.sax.saxutils import unescape

import qrcode
import requests
import xmltodict
from fake_useragent import UserAgent
from requests_toolbelt import sessions
from requests_toolbelt.downloadutils import stream

FILE_HELPER = "filehelper"
RECOMMEND_HELPER = "fmessage"
NEWS_APP = "newsapp"
WEIXIN = "weixin"


class ContactFlag(IntFlag):
    BLACKLIST = 8
    NOTIFY_CLOSE = 0x200
    TOP = 0x800


class VerifyFlag(IntFlag):
    BIZ_BRAND = 8


class MsgType(IntEnum):
    TEXT = 1
    IMAGE = 3
    VOICE = 34
    SHARE_CARD = 42
    VIDEO = 43
    EMOTICON = 47
    LOCATION = 48
    APP = 49
    STATUS_NOTIFY = 51
    VOIP_INVITE = 53
    SYS = 10000
    RECALLED = 10002


class StatusNotifyCode(IntEnum):
    READED = 1
    ENTER_SESSION = 2
    INITED = 3
    SYNC_CONV = 4


class AppMsgType(IntEnum):
    URL = 5
    ATTACH = 6
    REALTIME_SHARE_LOCATION = 17
    TRANSFERS = 2000


class MediaType(IntEnum):
    ATTACHMENT = 4


class CmdId(IntEnum):
    MOD_REMARK_NAME = 2
    TOP_CONTACT = 3


@dataclass
class Base:
    @classmethod
    def create(cls, d):
        return cls(**cls.coerce(d))

    @classmethod
    def coerce(cls, d):
        res = {}

        hints = get_dataclass_hints(cls)

        for key, value in d.items():
            key = to_snake(key)

            if key in hints:
                typ = hints[key]

                if issubclass(typ, Base):
                    value = typ.create(value)
                else:
                    if typing.get_origin(typ) is list:
                        args = typing.get_args(typ)

                        if args:
                            arg = args[0]

                            if issubclass(arg, Base):
                                value = list(map(arg.create, value))

                res[key] = value

        return res


def get_dataclass_hints(class_or_instance):
    hints = typing.get_type_hints(class_or_instance)

    return {field.name: hints[field.name] for field in fields(class_or_instance)}


def to_snake(s):
    return re.sub("(?<=[^_])((?=[A-Z][a-z])|(?<=[^A-Z])(?=[A-Z]))", "_", s).lower()


@dataclass
class UserBase(Base):
    user_name: str
    nick_name: str

    def notify(self, code):
        return notify(code, self.user_name)


@dataclass
class UserInfoBase(UserBase):
    head_img_url: str = field(repr=False)
    remark_name: str = field(repr=False)

    hide_input_bar_flag: int
    star_friend: int
    app_account_flag: int
    contact_flag: int
    sns_flag: int


@dataclass
class User(UserInfoBase):
    uin: int
    sex: int
    signature: str
    verify_flag: int
    web_wx_plugin_switch: int
    head_img_flag: int


@dataclass
class Member(UserBase):
    attr_status: int
    member_status: int
    display_name: str
    key_word: str


@dataclass
class Contact(UserInfoBase):
    member_list: list[Member]
    sex: int
    signature: str
    verify_flag: int
    owner_uin: int
    statues: int
    attr_status: int
    province: str
    city: str
    alias: str
    uni_friend: int
    display_name: str
    chat_room_id: int
    key_word: str
    encry_chat_room_id: str
    is_owner: int

    head_img_update_flag: int = 0
    contact_type: int = 0
    chat_room_owner: str = ""

    def __post_init__(self):
        self.is_me = is_me(self.user_name)
        self.is_room = is_room_contact(self.user_name)
        self.is_file_helper = is_file_helper(self.user_name)
        self.is_recommend_helper = is_recommend_helper(self.user_name)
        self.is_news_app = is_news_app(self.user_name)

    @property
    def is_black(self):
        return bool(self.contact_flag & ContactFlag.BLACKLIST)

    @property
    def is_brand(self):
        return bool(self.verify_flag & VerifyFlag.BIZ_BRAND)

    @property
    def is_muted(self):
        if self.is_room:
            return self.statues == 0
        else:
            return bool(self.contact_flag & ContactFlag.NOTIFY_CLOSE)

    @property
    def is_top(self):
        return bool(self.contact_flag & ContactFlag.TOP)

    @property
    def has_photo_album(self):
        return bool(self.sns_flag & 1)

    def send(self, content):
        return send(content, self.user_name)

    def send_img(self, path="", media_id=""):
        if not media_id:
            media_id = self.upload(path)

        return send_img(media_id, self.user_name)

    def send_video(self, path="", media_id=""):
        if not media_id:
            media_id = self.upload(path)

        return send_video(media_id, self.user_name)

    def send_app(self, path="", title="", total_len=0, attach_id=""):
        if not attach_id:
            if not title:
                title = os.path.basename(path)
            if not total_len:
                total_len = os.path.getsize(path)

            attach_id = self.upload(path)

        return send_app(title, total_len, attach_id, self.user_name)

    def send_emoticon(self, path="", media_id=""):
        if not media_id:
            media_id = self.upload(path)

        return send_emoticon(media_id, self.user_name)

    def revoke(self, svr_msg_id):
        revoke(svr_msg_id, self.user_name)

    def upload(self, path):
        return upload(path, self.user_name)

    def add_members(self, members):
        user_names = [m.user_name for m in members]

        if len(self.member_list) + len(user_names) < 40:
            add_members(self.user_name, user_names)
        else:
            invite_members(self.user_name, user_names)

    def update(self, d):
        d = self.coerce(d)

        for key, value in d.items():
            if value:
                setattr(self, key, value)


@dataclass
class RecommendInfo(UserBase):
    qq_num: int
    province: str
    city: str
    content: str
    signature: str
    alias: str
    scene: int
    verify_flag: int
    attr_status: int
    sex: int
    ticket: str
    op_code: int


@dataclass
class AppInfo(Base):
    app_id: str
    type: int


@dataclass
class Msg(Base):
    msg_id: str
    from_user_name: str
    to_user_name: str
    msg_type: int
    content: str
    status: int
    img_status: int
    create_time: int
    voice_length: int
    play_length: int
    file_name: str
    file_size: str
    media_id: str
    url: str
    app_msg_type: int
    status_notify_code: int
    status_notify_user_name: str
    recommend_info: RecommendInfo
    forward_flag: int
    app_info: AppInfo
    has_product_id: int
    ticket: str
    img_height: int
    img_width: int
    sub_msg_type: int
    new_msg_id: int
    ori_content: str
    encry_file_name: str

    def __post_init__(self):
        self.is_send = is_me(self.from_user_name)
        self.peer_user_name = self.to_user_name if self.is_send else self.from_user_name
        self.is_room = is_room_contact(self.peer_user_name)

        if self.msg_type == MsgType.STATUS_NOTIFY:
            return

        content = render(self.content)

        if self.is_room:
            m = re.search("^(@[a-z0-9]*):\n(.*)", content)

            if m:
                self.sender = m[1]
                content = m[2]

        if self.msg_type == MsgType.APP:
            if self.app_msg_type in (
                AppMsgType.URL,
                AppMsgType.TRANSFERS,
                AppMsgType.REALTIME_SHARE_LOCATION,
            ):
                self.xml = parse_xml(unescape(content))
        elif self.msg_type == MsgType.EMOTICON:
            if not self.has_product_id:
                self.xml = parse_xml(unescape(content))
        elif self.msg_type == MsgType.TEXT:
            if is_news_app(self.from_user_name):
                self.xml = parse_xml(unescape(content))
            elif self.sub_msg_type == MsgType.LOCATION:
                self.location_desc, location_url = content.split(":\n")
                self.location_url = self.url or location_url

                self.xml = parse_xml(self.ori_content)
        elif self.msg_type == MsgType.RECALLED:
            self.xml = parse_xml(unescape(content))
        elif self.msg_type == MsgType.SHARE_CARD:
            self.xml = parse_xml(unescape(content))

            self.recommend_info.head_img_url = get_head_img_url(
                self.recommend_info.user_name
            )


def is_me(user_name):
    return user_name == user.user_name


def is_room_contact(user_name):
    return user_name.startswith("@@")


def is_file_helper(user_name):
    return user_name == FILE_HELPER


def is_recommend_helper(user_name):
    return user_name == RECOMMEND_HELPER


def is_news_app(user_name):
    return user_name == NEWS_APP


def is_weixin(user_name):
    return user_name == WEIXIN


class WeChatError(Exception): ...


def valid_json(r, *args, **kwargs):
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

s.hooks["response"] = valid_json

ua = UserAgent()
s.headers["User-Agent"] = ua.random

user = None
contacts = {}


def login():
    if user:
        r = s.get(f"/cgi-bin/mmwebwx-bin/webwxpushloginurl?uin={user.uin}")
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
            set_base_request(r.text)

            return True

        if code == "400":
            return False


def set_base_request(xml):
    root = parse_xml(xml)["error"]

    global base_request
    base_request = {"Sid": root["wxsid"], "Uin": int(root["wxuin"])}


def init():
    content = post_json("/cgi-bin/mmwebwx-bin/webwxinit", {})

    sync_key = content["SyncKey"]
    set_user_info(content["User"])

    contacts.clear()
    add_contacts(content["ContactList"])
    init_chats(content["ChatSet"])

    user.notify(StatusNotifyCode.INITED)

    seq = 0
    while True:
        r = s.get(f"/cgi-bin/mmwebwx-bin/webwxgetcontact?seq={seq}")
        content = r.json()

        add_contacts(content["MemberList"])

        seq = content["Seq"]
        if seq == 0:
            break

    return check_msg(sync_key)


def set_user_info(user_info):
    global user
    user = User.create(user_info)


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
                        f'{x["Key"]}_{x["Val"]}' for x in sync_check_key["List"]
                    ),
                },
            )
        except requests.ConnectionError as e:
            if not isinstance(e.args[0].args[1], BadStatusLine):  # HTTP/1.1 0 -\r\n
                raise

            continue

        m = re.search('window.synccheck={retcode:"(.*)",selector:"(.*)"}', r.text)

        if m[1] != "0":
            logout()
            return

        msgs = []

        if m[2] != "0":
            content = post_json("/cgi-bin/mmwebwx-bin/webwxsync", {"SyncKey": sync_key})

            sync_check_key = content["SyncCheckKey"]
            sync_key = content["SyncKey"]

            add_contacts(content["ModContactList"])
            del_contacts(content["DelContactList"])

            msgs = process_msgs(content["AddMsgList"])

        yield msgs


def process_msgs(msgs):
    res = []
    status_notify_user_names = []

    for msg in msgs:
        m = Msg.create(msg)

        if m.status_notify_code == StatusNotifyCode.SYNC_CONV:
            status_notify_user_names.append(m.status_notify_user_name)

        res.append(m)

    if status_notify_user_names:
        init_chats(",".join(status_notify_user_names))

    return res


def init_chats(user_names):
    if isinstance(user_names, str):
        user_names = user_names.split(",")

    users = [
        {"UserName": user_name} for user_name in user_names if user_name not in contacts
    ]
    if users:
        add_contacts(batch_get_contacts(users))


def batch_get_contacts(users):
    return post_json(
        "/cgi-bin/mmwebwx-bin/webwxbatchgetcontact",
        {"Count": len(users), "List": users},
    )["ContactList"]


def add_contacts(contacts):
    for contact in contacts:
        add_contact(contact)


def del_contacts(contacts):
    for contact in contacts:
        del_contact(contact)


def add_contact(contact):
    user_name = contact["UserName"]

    if user_name in contacts:
        c = contacts[user_name]
        c.update(contact)
    else:
        c = Contact.create(contact)
        contacts[user_name] = c

    c.display_name = render(c.remark_name or c.nick_name)

    for m in c.member_list:
        m.display_name = render(m.display_name)
        m.head_img_url = get_head_img_url(
            m.user_name, chat_room_id=c.encry_chat_room_id
        )


def del_contact(contact):
    user_name = contact["UserName"]

    del contacts[user_name]


def render(s):
    def repl(m):
        code = m[1]

        if "2320e3" <= code <= "3920e3":
            return hexchr(code[:2]) + "\ufe0f\u20e3"  # keycap

        return hexchr(code)

    s = s.replace("<br/>", "\n")
    return re.sub('<span class="emoji emoji(.*?)"></span>', repl, s)


def hexchr(x):
    return chr(int(x, base=16))


def get_head_img_url(user_name, chat_room_id=""):
    return f"/cgi-bin/mmwebwx-bin/webwxgeticon?username={user_name}&chatroomid={chat_room_id}"


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
            "Content": to_xml(
                {
                    "appmsg": {
                        "title": title,
                        "type": AppMsgType.ATTACH.value,
                        "appattach": {"totallen": total_len, "attachid": attach_id},
                    }
                }
            ),
        },
    )


def parse_xml(xml):
    return xmltodict.parse(xml)


def to_xml(d):
    return xmltodict.unparse(d, full_document=False)


def send_emoticon(media_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendemoticon?fun=sys",
        {"ToUserName": to_user_name, "Type": MsgType.EMOTICON, "MediaId": media_id},
    )


def post_msg(url, msg):
    client_msg_id = time.time_ns()

    return post_json(
        url,
        {
            "Msg": {
                "ClientMsgId": client_msg_id,
                "LocalID": client_msg_id,
                "FromUserName": user.user_name,
                **msg,
            }
        },
    )["MsgID"]


def revoke(svr_msg_id, to_user_name):
    post_json(
        "/cgi-bin/mmwebwx-bin/webwxrevokemsg",
        {
            "SvrMsgId": svr_msg_id,
            "ToUserName": to_user_name,
            "ClientMsgId": time.time_ns(),
        },
    )


def notify(code, to_user_name):
    return post_json(
        "/cgi-bin/mmwebwx-bin/webwxstatusnotify",
        {
            "Code": code,
            "FromUserName": user.user_name,
            "ToUserName": to_user_name,
            "ClientMsgId": time.time_ns(),
        },
    )["MsgID"]


def upload(path, to_user_name):
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
                "ClientMediaId": time.time_ns(),
                "TotalLen": total_len,
                "StartPos": 0,
                "DataLen": total_len,
                "MediaType": MediaType.ATTACHMENT,
                "FromUserName": user.user_name,
                "ToUserName": to_user_name,
            }
        )

        chunk_size = int(0.5 * 1024 * 1024)
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


def mod_remark_name(user_name, remark_name):
    oplog(
        {
            "UserName": user_name,
            "CmdId": CmdId.MOD_REMARK_NAME,
            "RemarkName": remark_name,
        }
    )


def set_top_contact(user_name, op):
    oplog({"UserName": user_name, "CmdId": CmdId.TOP_CONTACT, "OP": op})


def oplog(data):
    post_json("/cgi-bin/mmwebwx-bin/webwxoplog", data)


def create_chat_room(members, topic=""):
    return post_json(
        "/cgi-bin/mmwebwx-bin/webwxcreatechatroom",
        {"MemberCount": len(members), "MemberList": members, "Topic": topic},
    )["ChatRoomName"]


def add_members(chat_room_name, members):
    if not isinstance(members, str):
        members = ",".join(members)

    update_chat_room(
        "addmember", {"ChatRoomName": chat_room_name, "AddMemberList": members}
    )


def del_members(chat_room_name, members):
    if not isinstance(members, str):
        members = ",".join(members)

    update_chat_room(
        "delmember", {"ChatRoomName": chat_room_name, "DelMemberList": members}
    )


def invite_members(chat_room_name, members):
    if not isinstance(members, str):
        members = ",".join(members)

    update_chat_room(
        "invitemember", {"ChatRoomName": chat_room_name, "InviteMemberList": members}
    )


def quit_chat_room(chat_room_name):
    update_chat_room("quitchatroom", {"ChatRoomName": chat_room_name})


def mod_topic(chat_room_name, new_topic):
    update_chat_room(
        "modtopic", {"ChatRoomName": chat_room_name, "NewTopic": new_topic}
    )


def update_chat_room(fun, data):
    post_json(f"/cgi-bin/mmwebwx-bin/webwxupdatechatroom?fun={fun}", data)


def post_json(url, data):
    payload = {"BaseRequest": base_request, **data}

    r = s.post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    )
    return r.json()


def check_url(url):
    r = s.get(f"/cgi-bin/mmwebwx-bin/webwxcheckurl?requrl={url}", allow_redirects=False)
    content = r.json()

    return content["FullURL"]
