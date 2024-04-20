import re

import qrcode
import xmltodict


def to_snake(s):
    return re.sub("(?<=[^_])((?=[A-Z][a-z])|(?<=[^A-Z])(?=[A-Z]))", "_", s).lower()


def print_qr(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.print_ascii()


def parse_xml(xml):
    return xmltodict.parse(xml)


def to_xml(d):
    return xmltodict.unparse(d, full_document=False)
