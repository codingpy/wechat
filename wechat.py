import re
import time
import json
import mimetypes
import math
import enum

import requests
import qrcode


CHUNK_SIZE = int(0.5 * 1024 * 1024)


class MsgType(enum.Enum):
    TEXT = 1
    IMAGE = 3
    VIDEO = 43
    EMOTICON = 47


class AppMsgType(enum.Enum):
    ATTACH = 6


class MediaType(enum.Enum):
    ATTACHMENT = 4


def utf_8(r, *args, **kwargs):
    r.encoding = 'utf-8'


s = requests.Session()

s.hooks['response'] = utf_8

user = {}

contacts = {}

base_request = {}


def login():
    r = s.get('https://login.wx.qq.com/jslogin', params={'appid': 'wx782c26e4c19acffb'})

    uuid = re.search('window.QRLogin.uuid = "(.*)"', r.text)[1]

    print_qr('https://login.weixin.qq.com/l/' + uuid)

    redirect_uri = check_login(uuid)

    if not redirect_uri:
        return

    r = s.get(redirect_uri, allow_redirects=False)

    sid = re.search('<wxsid>(.*)</wxsid>', r.text)[1]
    uin = re.search('<wxuin>(.*)</wxuin>', r.text)[1]

    base_request.update({
        'Sid': sid,
        'Uin': int(uin),
    })


def print_qr(data):
    qr = qrcode.QRCode()

    qr.add_data(data)

    qr.print_ascii()


def check_login(uuid):
    while True:
        r = s.get('https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login', params={'uuid': uuid})

        code = re.search('window.code=(\d+)', r.text)[1]

        if code == '200':
            return re.search('window.redirect_uri="(.*)"', r.text)[1]

        if code == '400':
            return


def init():
    r = s.post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxinit', json={'BaseRequest': {}})

    content = r.json()

    sync_key = content['SyncKey']

    user.update(
        content['User']
    )

    add_contact(user)

    for contact in content['ContactList']:
        add_contact(contact)

    chats = [{'UserName': user_name} for user_name in content['ChatSet'].split(',')]

    r = s.post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxbatchgetcontact', json={
        'BaseRequest': {},
        'Count': len(chats),
        'List': chats,
    })

    content = r.json()

    for contact in content['ContactList']:
        add_contact(contact)

    r = s.get('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact')

    content = r.json()

    for contact in content['MemberList']:
        add_contact(contact)

    return sync(sync_key)


def sync(sync_key):
    sync_check_key = sync_key

    while True:
        try:
            r = s.get('https://webpush.wx2.qq.com/cgi-bin/mmwebwx-bin/synccheck', params={
                'sid': base_request['Sid'],
                'uin': base_request['Uin'],
                'synckey': '|'.join(
                    f'{x["Key"]}_{x["Val"]}' for x in sync_check_key['List']
                ),
            })

            m = re.search('window.synccheck={retcode:"(.*)",selector:"(.*)"}', r.text)

            retcode = m[1]

            if retcode == '0':
                msgs = []

                selector = m[2]

                if selector != '0':
                    r = s.post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsync', json={
                        'BaseRequest': {},
                        'SyncKey': sync_key,
                    })

                    content = r.json()

                    sync_check_key = content['SyncCheckKey']
                    sync_key = content['SyncKey']

                    for contact in content['ModContactList']:
                        add_contact(contact)

                    for contact in content['DelContactList']:
                        del_contact(contact)

                    msgs = content['AddMsgList']

                yield msgs
            else:
                logout()

                return
        except requests.ConnectionError:
            pass


def add_contact(contact):
    contacts[contact['UserName']] = contact


def del_contact(contact):
    del contacts[contact['UserName']]


def logout():
    s.post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxlogout')


def send(content, to):
    return post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg', {
        'ToUserName': to,
        'Type': MsgType.TEXT.value,
        'Content': content,
    })


def send_img(media_id, to):
    return post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsgimg?fun=async&f=json', {
        'ToUserName': to,
        'Type': MsgType.IMAGE.value,
        'MediaId': media_id,
    })


def send_video(media_id, to):
    return post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendvideomsg?f=json', {
        'ToUserName': to,
        'Type': MsgType.VIDEO.value,
        'MediaId': media_id,
    })


def send_app(title, total_len, attach_id, to):
    return post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendappmsg', {
        'ToUserName': to,
        'Type': AppMsgType.ATTACH.value,
        'Content': (
            f'<appmsg>'
            f'  <title>{title}</title>'
            f'  <type>{AppMsgType.ATTACH.value}</type>'
            f'  <appattach>'
            f'    <totallen>{total_len}</totallen>'
            f'    <attachid>{attach_id}</attachid>'
            f'  </appattach>'
            f'</appmsg>'
        ),
    })


def send_emoticon(media_id, to):
    return post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendemoticon?fun=sys', {
        'ToUserName': to,
        'Type': MsgType.EMOTICON.value,
        'MediaId': media_id,
    })


def post(url, msg):
    client_msg_id = time.time_ns()

    payload = {
        'BaseRequest': base_request,
        'Msg': {
            'ClientMsgId': client_msg_id,
            'LocalID': client_msg_id,
            'FromUserName': user['UserName'],
            **msg,
        },
    }

    r = s.post(url, data=json.dumps(payload, ensure_ascii=False).encode())

    content = r.json()

    if content['BaseResponse']['Ret'] == 0:
        return content['MsgID']


def revoke(svr_msg_id, to):
    r = s.post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxrevokemsg', json={
        'BaseRequest': {},
        'SvrMsgId': svr_msg_id,
        'ToUserName': to,
        'ClientMsgId': time.time_ns(),
    })

    content = r.json()

    return content['BaseResponse']['Ret']


def upload(file, to='filehelper'):
    client_media_id = time.time_ns()

    ctype, encoding = mimetypes.guess_type(file)

    if ctype is None or encoding is not None:
        ctype = 'application/octet-stream'

    maintype, subtype = ctype.split('/')

    if maintype == 'image' and subtype != 'gif':
        mediatype = 'pic'
    elif maintype == 'video':
        mediatype = 'video'
    else:
        mediatype = 'doc'

    with open(file, 'rb') as f:
        total_len = f.seek(0, 2)

        f.seek(0)

        chunks = math.ceil(total_len / CHUNK_SIZE)

        for chunk in range(chunks):
            r = s.post('https://file.wx2.qq.com/cgi-bin/mmwebwx-bin/webwxuploadmedia', params={'f': 'json'}, files={'filename': f.read(CHUNK_SIZE)}, data={
                'chunks': chunks,
                'chunk': chunk,
                'mediatype': mediatype,
                'uploadmediarequest': json.dumps({
                    'BaseRequest': base_request,
                    'ClientMediaId': client_media_id,
                    'TotalLen': total_len,
                    'StartPos': 0,
                    'DataLen': total_len,
                    'MediaType': MediaType.ATTACHMENT.value,
                    'ToUserName': to,
                }),
            })

    content = r.json()

    if content['BaseResponse']['Ret'] == 0:
        return content['MediaId']


def get_img(msg_id, out):
    download('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetmsgimg?MsgID=' + msg_id, out)


def download(url, out):
    r = s.get(url, stream=True)

    with open(out, 'wb') as f:
        for chunk in r.iter_content(chunk_size=128):
            f.write(chunk)
