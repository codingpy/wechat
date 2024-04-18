import qrcode
import xmltodict


def print_qr(data):
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.print_ascii()


def parse_xml(xml):
    return xmltodict.parse(xml)


def to_xml(d):
    return xmltodict.unparse(d, full_document=False)
