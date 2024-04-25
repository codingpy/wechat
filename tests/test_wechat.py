import wechat


def test_send(response_mock):
    response_mock.post(
        "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg",
        json={"BaseResponse": {"Ret": 0, "ErrMsg": ""}, "MsgID": "9947253044869834033"},
    )

    msg_id = wechat.send(
        "Message thus with.",
        "@@a206ff4c10541070ed74bd5a4affd0388f6f69cca36b37b08a40dc9b544bdbf0",
    )
    assert msg_id == "9947253044869834033"
