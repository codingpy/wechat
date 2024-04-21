from enum import IntEnum, IntFlag

FILE_HELPER = "filehelper"
RECOMMEND_HELPER = "fmessage"
NEWS_APP = "newsapp"
WEIXIN = "weixin"


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


class AppMsgType(IntEnum):
    AUDIO = 3
    VIDEO = 4
    URL = 5
    ATTACH = 6
    REALTIME_SHARE_LOCATION = 17
    TRANSFERS = 2000


class MediaType(IntEnum):
    ATTACHMENT = 4


class StatusNotifyCode(IntEnum):
    READED = 1
    ENTER_SESSION = 2
    INITED = 3
    SYNC_CONV = 4


class CmdId(IntEnum):
    MOD_REMARK_NAME = 2
    TOP_CONTACT = 3


class ContactFlag(IntFlag):
    BLACKLIST = 8
    NOTIFY_CLOSE = 0x200
    TOP_CONTACT = 0x800


class VerifyFlag(IntFlag):
    BIZ_BRAND = 8
