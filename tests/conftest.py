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

        yield m
