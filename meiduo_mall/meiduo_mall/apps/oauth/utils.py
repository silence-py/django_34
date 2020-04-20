from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, BadData
from django.conf import settings


def generate_openid_signature(raw_openid):
    """加密"""
    # 创建加密对象
    serializer = Serializer(settings.SECRET_KEY, 600)
    # 加密并包装为字典格式
    openid_dict = {'openid': raw_openid}
    openid = serializer.dumps(openid_dict)
    # 解码
    return openid.decode()


def check_openid(openid):
    """解密"""
    # 创建解密对象
    serializer = Serializer(settings.SECRET_KEY, 600)
    try:
        data = serializer.loads(openid)
        openid = data.get('openid')
        return openid
    except BadData:
        return None