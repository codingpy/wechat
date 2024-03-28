import pytest
import responses


@pytest.fixture
def response_mock():
    with responses.RequestsMock() as m:
        uuid = "4aDCd-Nv9g=="
        redirect_uri = "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxnewloginpage?ticket=Awgd0-v_fqfwMrdXcthYCYeK@qrticket_0"

        sid = "3jFaxE9UDfEa8H+U"
        uin = 1217252163

        m.get(
            "https://login.wx.qq.com/jslogin?appid=wx782c26e4c19acffb",
            body=f'window.QRLogin.code = 200; window.QRLogin.uuid = "{uuid}"',
        )

        m.get(
            f"https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login?uuid={uuid}",
            body="window.code=201;",
        )
        m.get(
            f"https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login?uuid={uuid}",
            body=f'window.code=200;\nwindow.redirect_uri="{redirect_uri}";',
        )

        m.get(
            redirect_uri,
            body=f"<error><wxsid>{sid}</wxsid><wxuin>{uin}</wxuin></error>",
            status=301,
        )

        m.post(
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
                        "HideInputBarFlag": 0,
                        "Sex": 1,
                        "Signature": "Because painting suffer store structure sign expect.",
                        "VerifyFlag": 0,
                        "StarFriend": 0,
                        "Statues": 0,
                        "AttrStatus": 102945,
                        "Province": "",
                        "City": "",
                        "Alias": "",
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
                    "HideInputBarFlag": 0,
                    "Sex": 1,
                    "Signature": "Customer source general where thus.",
                    "AppAccountFlag": 0,
                    "VerifyFlag": 0,
                    "ContactFlag": 0,
                    "WebWxPluginSwitch": 0,
                    "HeadImgFlag": 1,
                    "SnsFlag": 1,
                },
                "ChatSet": "@@a206ff4c10541070ed74bd5a4affd0388f6f69cca36b37b08a40dc9b544bdbf0,",
            },
        )

        yield m
