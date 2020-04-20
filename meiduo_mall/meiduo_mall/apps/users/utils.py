from django.contrib.auth.backends import ModelBackend
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.shortcuts import render
from django.conf import settings
from .models import User
import re


# 判断用户输入的帐号类型
def get_user_by_account(account):
    try:
        if re.match(r'^1[3-9]\d{9}$', account):
            user = User.objects.get(mobile=account)
        else:
            user = User.objects.get(username=account)
        return user
    except User.DoesNotExist:
        return None


class UsernameMobileAuthBackend(ModelBackend):
    # 重写用户登录认证方法
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = get_user_by_account(username)

        if user and user.check_password(password):
            return user


def generate_verify_email_url(user):
    # 创建加密对象
    serializer = Serializer(secret_key=settings.SECRET_KEY, expires_in=600)

    # 拼接路径
    # 'http://www.meiduo.site:8000/emails/verification/' + '?token=' + token
    data = {'user_id': user.id, 'email': user.email}

    # 对数据加密
    token = serializer.dumps(data).decode()

    verify_url = 'http://www.meiduo.site:8000/emails/verification/'+ '?token=' + token

    return verify_url


def check_email(data):

    # 创建解密对象
    serializer = Serializer(secret_key=settings.SECRET_KEY, expires_in=600)

    token_dict = serializer.loads(data)

    return token_dict
