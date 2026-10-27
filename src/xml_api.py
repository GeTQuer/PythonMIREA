from xml.etree import ElementTree


def encode(value):
    """Преобразовать записи сервера в XML-ответ."""
    root = ElementTree.Element("response")
    records = value if isinstance(value, list) else [value]
    for record in records:
        item = ElementTree.SubElement(root, "item")
        for name, content in record.items():
            field = ElementTree.SubElement(item, name)
            if content is None:
                field.set("null", "true")
            else:
                field.text = str(content)
    return ElementTree.tostring(root, encoding="utf-8")


def decode(data):
    """Прочитать XML-ответ и вернуть список словарей."""
    root = ElementTree.fromstring(data)
    return [
        {field.tag: None if field.get("null") else field.text or ""
         for field in item}
        for item in root
    ]


def request_body(fields):
    """Преобразовать поля запроса в XML-тело."""
    root = ElementTree.Element("request")
    for name, value in fields.items():
        ElementTree.SubElement(root, name).text = str(value)
    return ElementTree.tostring(root, encoding="utf-8")
