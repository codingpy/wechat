import pytest
import responses

import wechat


@pytest.fixture
def response_mock():
    with responses.RequestsMock() as mock:
        yield mock


@pytest.fixture(autouse=True)
def msgs(response_mock):
    uuid = "4aDCd-Nv9g=="
    redirect_uri = "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxnewloginpage?ticket=Awgd0-v_fqfwMrdXcthYCYeK@qrticket_0"

    sid = "3jFaxE9UDfEa8H+U"
    uin = 1217252163

    response_mock.get(
        "https://login.wx2.qq.com/jslogin?appid=wx782c26e4c19acffb",
        body=f'window.QRLogin.code = 200; window.QRLogin.uuid = "{uuid}"',
    )
    response_mock.get(
        f"https://login.wx2.qq.com/cgi-bin/mmwebwx-bin/login?uuid={uuid}",
        body="window.code=201;",
    )
    response_mock.get(
        f"https://login.wx2.qq.com/cgi-bin/mmwebwx-bin/login?uuid={uuid}",
        body=f'window.code=200;\nwindow.redirect_uri="{redirect_uri}";',
    )
    response_mock.get(
        redirect_uri,
        body=f"<error><wxsid>{sid}</wxsid><wxuin>{uin}</wxuin></error>",
        status=301,
    )
    response_mock.post(
        "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxinit",
        json={
            "BaseResponse": {"Ret": 0, "ErrMsg": ""},
            "ContactList": [
                {
                    "UserName": "@15935d3e04fa3eabf2047f04f288049bdc0afa9b33633658542519b5a9755d37",
                    "NickName": "dflowers",
                    "HeadImgUrl": "/cgi-bin/mmwebwx-bin/webwxgeticon?username=@15935d3e04fa3eabf2047f04f288049bdc0afa9b33633658542519b5a9755d37",
                    "ContactFlag": 3,
                    "MemberList": [],
                    "RemarkName": "Mark Larson",
                    "Sex": 1,
                    "Signature": "Because painting suffer store structure sign expect.",
                    "VerifyFlag": 0,
                    "StarFriend": 0,
                    "Statues": 0,
                    "AttrStatus": 102945,
                    "Province": "",
                    "City": "",
                    "SnsFlag": 257,
                    "DisplayName": "",
                    "KeyWord": "",
                    "EncryChatRoomId": "",
                    "IsOwner": 0,
                }
            ],
            "SyncKey": {
                "Count": 4,
                "List": [
                    {"Key": 1, "Val": 791415259},
                    {"Key": 2, "Val": 0},
                    {"Key": 3, "Val": 791410901},
                    {"Key": 1000, "Val": 1711670660},
                ],
            },
            "User": {
                "Uin": uin,
                "UserName": "@bc8caea848b60ff68b0449faa9c8d065f36876a8c8b114d9cdc562a9f18fe49e",
                "NickName": "udavis",
                "HeadImgUrl": "/cgi-bin/mmwebwx-bin/webwxgeticon?username=@bc8caea848b60ff68b0449faa9c8d065f36876a8c8b114d9cdc562a9f18fe49e",
                "Sex": 1,
                "Signature": "Customer source general where thus.",
                "SnsFlag": 1,
            },
            "ChatSet": "@@a206ff4c10541070ed74bd5a4affd0388f6f69cca36b37b08a40dc9b544bdbf0,",
        },
    )
    response_mock.post(
        "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxstatusnotify",
        json={"BaseResponse": {"Ret": 0, "ErrMsg": ""}, "MsgID": "2518347772561648129"},
    )
    response_mock.get(
        "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?seq=0",
        json={
            "BaseResponse": {"Ret": 0, "ErrMsg": ""},
            "MemberList": [
                {
                    "UserName": "@@255f17df1bd8a28b7f165fa894b387368cedaf09a6f9782bb42479cd9ae4c8a7",
                    "NickName": "shannon70",
                    "HeadImgUrl": "/cgi-bin/mmwebwx-bin/webwxgetheadimg?username=@@255f17df1bd8a28b7f165fa894b387368cedaf09a6f9782bb42479cd9ae4c8a7",
                    "ContactFlag": 3,
                    "MemberList": [],
                    "RemarkName": "",
                    "Sex": 0,
                    "Signature": "",
                    "VerifyFlag": 0,
                    "StarFriend": 0,
                    "Statues": 0,
                    "AttrStatus": 0,
                    "Province": "",
                    "City": "",
                    "SnsFlag": 0,
                    "DisplayName": "",
                    "KeyWord": "",
                    "EncryChatRoomId": "",
                    "IsOwner": 0,
                }
            ],
            "Seq": 0,
        },
    )
    response_mock.post(
        "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxbatchgetcontact",
        json={
            "BaseResponse": {"Ret": 0, "ErrMsg": ""},
            "ContactList": [
                {
                    "UserName": "@@a206ff4c10541070ed74bd5a4affd0388f6f69cca36b37b08a40dc9b544bdbf0",
                    "NickName": "drivera",
                    "HeadImgUrl": "/cgi-bin/mmwebwx-bin/webwxgetheadimg?username=@@a206ff4c10541070ed74bd5a4affd0388f6f69cca36b37b08a40dc9b544bdbf0",
                    "ContactFlag": 2,
                    "MemberList": [
                        {
                            "UserName": "@5adfb4b10e294fe7ddee1e4f7af82f9ada0db851877461a8a2ac4bf6b3f37c5b",
                            "NickName": "rochaerin",
                            "AttrStatus": 16879713,
                            "MemberStatus": 0,
                            "DisplayName": "",
                            "KeyWord": "",
                        },
                        {
                            "UserName": "@2021f2673fd5389e82f9916db3909824c397c856461418a1bb7b8b4ed8c062b0",
                            "NickName": "smitholivia",
                            "AttrStatus": 99711,
                            "MemberStatus": 0,
                            "DisplayName": "",
                            "KeyWord": "sxf",
                        },
                        {
                            "UserName": "@bc8caea848b60ff68b0449faa9c8d065f36876a8c8b114d9cdc562a9f18fe49e",
                            "NickName": "udavis",
                            "AttrStatus": 33656933,
                            "MemberStatus": 0,
                            "DisplayName": "Matthew Washington",
                            "KeyWord": "",
                        },
                    ],
                    "RemarkName": "",
                    "Sex": 0,
                    "Signature": "",
                    "VerifyFlag": 0,
                    "StarFriend": 0,
                    "Statues": 0,
                    "AttrStatus": 0,
                    "Province": "",
                    "City": "",
                    "SnsFlag": 0,
                    "DisplayName": "",
                    "KeyWord": "",
                    "EncryChatRoomId": "@e619b0e9ed8896ea8f523e105ac5bd2c",
                    "IsOwner": 0,
                },
                {
                    "UserName": "@@255f17df1bd8a28b7f165fa894b387368cedaf09a6f9782bb42479cd9ae4c8a7",
                    "NickName": "shannon70",
                    "HeadImgUrl": "/cgi-bin/mmwebwx-bin/webwxgetheadimg?username=@@255f17df1bd8a28b7f165fa894b387368cedaf09a6f9782bb42479cd9ae4c8a7",
                    "ContactFlag": 3,
                    "MemberList": [
                        {
                            "UserName": "@0c1490eb5b1c530edcedae6a2743684f94841e1c8383c83b4b570aea77f8f344",
                            "NickName": "rachel57",
                            "AttrStatus": 102501,
                            "MemberStatus": 0,
                            "DisplayName": "Aaron Lyons",
                            "KeyWord": "",
                        },
                        {
                            "UserName": "@bc8caea848b60ff68b0449faa9c8d065f36876a8c8b114d9cdc562a9f18fe49e",
                            "NickName": "udavis",
                            "AttrStatus": 33656933,
                            "MemberStatus": 0,
                            "DisplayName": "Matthew Washington",
                            "KeyWord": "",
                        },
                        {
                            "UserName": "@034e501512199a6b35911fe26abebea9bd4a965302b416ecbe2be458f499a10e",
                            "NickName": "cody96",
                            "AttrStatus": 102589,
                            "MemberStatus": 0,
                            "DisplayName": "",
                            "KeyWord": "",
                        },
                    ],
                    "RemarkName": "",
                    "Sex": 0,
                    "Signature": "",
                    "VerifyFlag": 0,
                    "StarFriend": 0,
                    "Statues": 0,
                    "AttrStatus": 0,
                    "Province": "",
                    "City": "",
                    "SnsFlag": 0,
                    "DisplayName": "",
                    "KeyWord": "",
                    "EncryChatRoomId": "@7452d30159d65cb1411e2f5463ebbd69",
                    "IsOwner": 0,
                },
            ],
        },
    )

    return wechat.login()
