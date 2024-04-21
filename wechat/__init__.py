import json
import math
import mimetypes
import os
import re
import time
from http.client import BadStatusLine
from xml.sax.saxutils import unescape

import requests
from fake_useragent import UserAgent
from requests_toolbelt import sessions
from requests_toolbelt.downloadutils import stream

from wechat import consts, models, utils


class WeChatError(Exception): ...


def raise_for_json(r, *args, **kwargs):
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
s.hooks["response"] = raise_for_json

user = None
contacts = {}

chats = []
users = []


def login():
    if user:
        r = s.get(f"/cgi-bin/mmwebwx-bin/webwxpushloginurl?uin={user.uin}")
        content = r.json()

        if content["ret"] == "0":
            uuid = content["uuid"]

            if check_login(uuid):
                return init()

    return login_qr()


def logout():
    s.post("/cgi-bin/mmwebwx-bin/webwxlogout")


def login_qr():
    ua = UserAgent(platforms="pc")
    s.headers["User-Agent"] = ua.random

    r = s.get("https://login.wx2.qq.com/jslogin?appid=wx782c26e4c19acffb")
    uuid = re.search('window.QRLogin.uuid = "(.*)"', r.text)[1]

    utils.print_qr(f"https://login.weixin.qq.com/l/{uuid}")

    if check_login(uuid):
        return init()


def check_login(uuid):
    while True:
        r = s.get(f"https://login.wx2.qq.com/cgi-bin/mmwebwx-bin/login?uuid={uuid}")
        code = re.search("window.code=(\d+)", r.text)[1]

        if code == "200":
            redirect_uri = re.search('window.redirect_uri="(.*)"', r.text)[1]

            r = s.get(redirect_uri, allow_redirects=False)
            set_base_request(r.text)

            return True

        if code == "400":
            return False


def set_base_request(xml):
    root = utils.parse_xml(xml)["error"]

    global base_request
    base_request = {"Sid": root["wxsid"], "Uin": int(root["wxuin"])}


def init():
    content = post_json("/cgi-bin/mmwebwx-bin/webwxinit", {})

    sync_key = content["SyncKey"]
    set_user_info(content["User"])

    contacts.clear()
    add_contacts(content["ContactList"])
    init_chats(content["ChatSet"])

    notify(consts.StatusNotifyCode.INITED, user.user_name)

    seq = 0
    while True:
        r = s.get(f"/cgi-bin/mmwebwx-bin/webwxgetcontact?seq={seq}")
        content = r.json()

        add_contacts(content["MemberList"])

        seq = content["Seq"]
        if seq == 0:
            break

    batch_add_contacts()

    return sync(sync_key)


def set_user_info(user_info):
    global user
    user = models.User(user_info)


def sync(sync_key):
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

            batch_add_contacts()

        yield msgs


def process_msgs(msgs):
    res = []

    for msg in msgs:
        M = models.Msg(msg)

        M.is_send = is_me(M.from_user_name)
        M.peer_user_name = M.to_user_name if M.is_send else M.from_user_name
        M.is_room = is_room_contact(M.peer_user_name)

        if M.msg_type == consts.MsgType.STATUS_NOTIFY:
            if M.status_notify_code == consts.StatusNotifyCode.SYNC_CONV:
                init_chats(M.status_notify_user_name)
        else:
            M.sender = M.from_user_name
            x = render(M.content)

            if M.is_room:
                m = re.search("^(@[a-z0-9]*):\n(.*)", x)
                if m:
                    M.sender = m[1]
                    x = m[2]

            match M.msg_type:
                case consts.MsgType.APP:
                    if M.app_msg_type in consts.AppMsgType:
                        x = utils.parse_xml(unescape(x))
                case consts.MsgType.EMOTICON:
                    if not M.has_product_id:
                        x = utils.parse_xml(unescape(x))
                case consts.MsgType.TEXT:
                    if is_news_app(M.from_user_name):
                        x = utils.parse_xml(unescape(x))
                    elif M.sub_msg_type == consts.MsgType.LOCATION:
                        M.location_desc, location_url = x.split(":\n")
                        M.location_url = M.url or location_url

                        M.ori_content = utils.parse_xml(M.ori_content)
                case consts.MsgType.RECALLED:
                    x = utils.parse_xml(unescape(x))
                case consts.MsgType.SHARE_CARD:
                    x = utils.parse_xml(unescape(x))

                    M.recommend_info.head_img_url = get_head_img_url(
                        M.recommend_info.user_name
                    )

            M.content = x

        res.append(M)

    return res


def init_chats(user_names):
    if isinstance(user_names, str):
        user_names = user_names.split(",")

    chats.clear()

    for user_name in user_names:
        if user_name:
            chats.append(user_name)

            if user_name not in contacts:
                users.append({"UserName": user_name})


def batch_add_contacts():
    if users:
        add_contacts(batch_get_contacts(users))
        users.clear()


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
        c = models.Contact(contact)
        contacts[user_name] = c

        c.is_room = is_room_contact(user_name)
        c.is_file_helper = is_file_helper(user_name)
        c.is_recommend_helper = is_recommend_helper(user_name)
        c.is_news_app = is_news_app(user_name)

    c.is_black = bool(c.contact_flag & consts.ContactFlag.BLACKLIST)
    c.is_brand = bool(c.verify_flag & consts.VerifyFlag.BIZ_BRAND)
    c.is_muted = bool(
        not c.statues if c.is_room else c.contact_flag & consts.ContactFlag.NOTIFY_CLOSE
    )
    c.is_top = bool(c.contact_flag & consts.ContactFlag.TOP_CONTACT)
    c.has_photo_album = bool(c.sns_flag & 1)

    c.display_name = render(c.remark_name or c.nick_name)

    if c.is_room:
        if c.member_list:
            for m in c.member_list:
                m.is_me = is_me(m.user_name)
                m.display_name = render(m.display_name)
                m.head_img_url = get_head_img_url(
                    m.user_name, chat_room_id=c.encry_chat_room_id
                )
        else:
            users.append({"UserName": user_name})


def del_contact(contact):
    user_name = contact["UserName"]

    del contacts[user_name]


def render(s):
    def repl(m):
        code = m[1]

        if is_keycap(code):
            return hexchr(code[:2]) + "\ufe0f\u20e3"
        if is_flag(code):
            return hexchr(code[:5]) + hexchr(code[5:])

        return hexchr(code)

    s = s.replace("<br/>", "\n")
    return re.sub('<span class="emoji emoji(.*?)"></span>', repl, s)


def is_keycap(code):
    return "2320e3" <= code.zfill(6) <= "3920e3"


def is_flag(code):
    return "1f1e6" * 2 <= code.zfill(10) <= "1f1ff" * 2


def hexchr(x):
    return chr(int(x, base=16))


def get_head_img_url(user_name, chat_room_id=""):
    if is_room_contact(user_name):
        url = "/cgi-bin/mmwebwx-bin/webwxgetheadimg"
    else:
        url = "/cgi-bin/mmwebwx-bin/webwxgeticon"

    url += f"?username={user_name}"
    if chat_room_id:
        url += f"&chatroomid={chat_room_id}"

    return url


def is_me(user_name):
    return user_name == user.user_name


def is_room_contact(user_name):
    return user_name.startswith("@@")


def is_file_helper(user_name):
    return user_name == consts.FILE_HELPER


def is_recommend_helper(user_name):
    return user_name == consts.RECOMMEND_HELPER


def is_news_app(user_name):
    return user_name == consts.NEWS_APP


def is_weixin(user_name):
    return user_name == consts.WEIXIN


def send(content, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendmsg",
        {"ToUserName": to_user_name, "Type": consts.MsgType.TEXT, "Content": content},
    )


def send_img(media_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendmsgimg?fun=async&f=json",
        {"ToUserName": to_user_name, "Type": consts.MsgType.IMAGE, "MediaId": media_id},
    )


def send_video(media_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendvideomsg?f=json",
        {"ToUserName": to_user_name, "Type": consts.MsgType.VIDEO, "MediaId": media_id},
    )


def send_app(title, total_len, attach_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendappmsg",
        {
            "ToUserName": to_user_name,
            "Type": consts.AppMsgType.ATTACH,
            "Content": utils.to_xml(
                {
                    "appmsg": {
                        "title": title,
                        "type": consts.AppMsgType.ATTACH.value,
                        "appattach": {"totallen": total_len, "attachid": attach_id},
                    }
                }
            ),
        },
    )


def send_emoticon(media_id, to_user_name):
    return post_msg(
        "/cgi-bin/mmwebwx-bin/webwxsendemoticon?fun=sys",
        {
            "ToUserName": to_user_name,
            "Type": consts.MsgType.EMOTICON,
            "MediaId": media_id,
        },
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
                "MediaType": consts.MediaType.ATTACHMENT,
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

    return r.json()["MediaId"]


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
            "CmdId": consts.CmdId.MOD_REMARK_NAME,
            "RemarkName": remark_name,
        }
    )


def set_top_contact(user_name, op):
    oplog({"UserName": user_name, "CmdId": consts.CmdId.TOP_CONTACT, "OP": op})


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

    return s.post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    ).json()


def check_url(url):
    r = s.get(f"/cgi-bin/mmwebwx-bin/webwxcheckurl?requrl={url}", allow_redirects=False)
    content = r.json()

    return content["FullURL"]
