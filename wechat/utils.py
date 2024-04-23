import re

import qrcode
import xmltodict


def to_snake(s):
    return re.sub("(?<=[^_])((?=[A-Z][a-z])|(?<=[^A-Z])(?=[A-Z]))", "_", s).lower()


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


def print_qr(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.print_ascii()


def parse_xml(xml):
    return xmltodict.parse(xml)


def to_xml(d):
    return xmltodict.unparse(d, full_document=False)
