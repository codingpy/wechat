import typing

from wechat import utils


class Base:
    def __init_subclass__(cls):
        cls.hints = typing.get_type_hints(cls)

    def update(self, d):
        for key, value in d.items():
            key = utils.to_snake(key)

            if key in self.hints:
                typ = self.hints[key]

                if typing.get_origin(typ) is list:
                    args = typing.get_args(typ)
                    if args:
                        value = list(map(args[0], value))
                else:
                    value = typ(value)

                setattr(self, key, value)

    __init__ = update


class User(Base):
    uin: int
    user_name: str
    nick_name: str
    head_img_url: str
    sex: int
    signature: str
    sns_flag: int


class Member(Base):
    user_name: str
    nick_name: str
    attr_status: int
    display_name: str
    key_word: str


class Contact(Member):
    head_img_url: str
    contact_flag: int
    member_list: list[Member]
    remark_name: str
    sex: int
    signature: str
    verify_flag: int
    star_friend: int
    statues: int
    province: str
    city: str
    sns_flag: int
    encry_chat_room_id: str
    is_owner: int

    chat_room_owner: str = ""


class RecommendInfo(Base):
    user_name: str
    nick_name: str
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


class AppInfo(Base):
    app_id: str
    type: int


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
