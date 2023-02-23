import re
import enum

import requests
import qrcode


class MsgType(enum.Enum):
    TEXT = 1


def utf_8(r, *args, **kwargs):
    r.encoding = 'utf-8'


s = requests.Session()

s.hooks['response'] = utf_8

user = {}

contacts = {}


def login():
    r = s.get('https://login.wx.qq.com/jslogin', params={'appid': 'wx782c26e4c19acffb'})

    uuid = re.search('window.QRLogin.uuid = "(.*)"', r.text)[1]

    print_qr('https://login.weixin.qq.com/l/' + uuid)

    while True:
        r = s.get('https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login', params={'uuid': uuid})

        m = re.search('window.redirect_uri="(.*)"', r.text)

        if m:
            break

    r = s.get(m[1], allow_redirects=False)

    sid = re.search('<wxsid>(.*)</wxsid>', r.text)[1]
    uin = re.search('<wxuin>(.*)</wxuin>', r.text)[1]

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

    return sync(sid, uin, sync_key)


def print_qr(data):
    qr = qrcode.QRCode()

    qr.add_data(data)

    qr.print_ascii()


def sync(sid, uin, sync_key):
    sync_check_key = sync_key

    while True:
        r = s.get('https://webpush.wx2.qq.com/cgi-bin/mmwebwx-bin/synccheck', params={
            'sid': sid,
            'uin': uin,
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


def add_contact(contact):
    contacts[contact['UserName']] = contact


def del_contact(contact):
    del contacts[contact['UserName']]


def logout():
    s.post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxlogout')


def send(msg, to):
    msg['FromUserName'] = user['UserName']
    msg['ToUserName'] = to

    r = s.post('https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg', json={
        'BaseRequest': {},
        'Msg': msg,
    })

    content = r.json()

    if content['BaseResponse']['Ret'] == 0:
        return content['MsgID']
