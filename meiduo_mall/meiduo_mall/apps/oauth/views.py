from django.shortcuts import render, redirect
from QQLoginTool.QQtool import OAuthQQ
from django.views import View
from django.http import JsonResponse, HttpResponseServerError, HttpResponseForbidden
from django.conf import settings
from django.contrib.auth import login
from django_redis import get_redis_connection
from users.models import User
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

import logging
import re

from meiduo_mall.utils.response_code import RETCODE
from.models import OAuthQQUser
from .utils import generate_openid_signature, check_openid
from carts.utils import merge_cart_cookie_to_redis

logger = logging.getLogger('django')


class QQOAuthURLView(View):
    def get(self, request):
        # 获取查询数据
        next_url = request.GET.get('next') or ('/')

        # 创建qq认证工具对象
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        state=next_url)

        # 拼接路径
        qq_url = oauth.get_qq_url()

        # 响应json数据

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'login_url': qq_url})


class QQOAuthUserView(View):

    def get(self, request):

        # 接收数据
        code = request.GET.get('code')
        # 校验数据
        if code is None:
            return HttpResponseForbidden('缺少必要参数')

        # 创建qq认证工具对象
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,)
        try:
            # 通过code获取token
            access_token = oauth.get_access_token(code)

            # 通过token获取openid
            openid = oauth.get_open_id(access_token)
        except Exception as e:
            logger.error('oauth2.0认证失败')
            return HttpResponseServerError("oauth2.0认证失败")

        try:
            # 通过openid查询用户是否绑定
            oauth_model = OAuthQQUser.objects.get(openid=openid)

        except OAuthQQUser.DoesNotExist:
            # 未绑定用户渲染

            # 对数据进行加密(默认为bytes类型)
            data = {'openid': generate_openid_signature(openid)}

            return render(request, 'oauth_callback.html', data)

        else:
            # 状态保持
            user = oauth_model.user
            login(request, user)
            # 重定向并设置cookie
            response = redirect(request.GET.get('state') or '/')
            # 合并购物车
            merge_cart_cookie_to_redis(request, response)
            response.set_cookie('username', user.username, max_age=3600*24*14)

            return response

    def post(self, request):
        # 获取数据
        query_dict = request.POST
        mobile = query_dict.get('mobile')
        password = query_dict.get('password')
        sms_code_client = query_dict.get('sms_code')
        openid = query_dict.get('openid')

        # 校验数据
        if all([mobile, password, sms_code_client, openid]) is False:
            return HttpResponseForbidden('缺少必要的参数')

        if not re.match('^1[3-9]\d{9}$', mobile):
            return HttpResponseForbidden('手机号格式错误')

        if not re.match('[0-9A-Za-z]{8,20}$', password):
            return HttpResponseForbidden('密码格式错误')

        redis_conn = get_redis_connection('verify_code')
        sms_code_server = redis_conn.get('sms_%s' % mobile)

        # 判断短信验证码是过期
        if sms_code_server is None:
            return render(request, 'oauth_callback.html', {'sms_code_errmsg': '短信验证码错误'})
        if sms_code_server.decode() != sms_code_client:
            return render(request, 'oauth_callback.html', {'sms_code_errmsg': '短信验证码错误'})

        # 创建解密对象
        openid = check_openid(openid)
        if openid is None:
            return HttpResponseForbidden('缺少必要的参数')

        # 判断用户是否已经注册过
        try:
            # 已注册用户校验用户密码是否正确
            user = User.objects.get(mobile=mobile)

        except:
            # 未注册用户创建新用户
            user = User.objects.create_user(username=mobile, password=password, mobile=mobile)
        else:
            if user.check_password(password) is False:
                content = {'qq_login_errmsg': '帐号或密码错误'}
                return render(request, 'oauth_callback.html', content)

        # 创建qq登录用户数据并绑定openid
        OAuthQQUser.objects.create(user=user, openid=openid)

        # 状态保持
        login(request, user)

        # 重定向并设置cookie
        response = redirect(request.GET.get('state') or '/')
        # 合并购物车
        merge_cart_cookie_to_redis(request, response)

        response.set_cookie('username', user.username, max_age=3600*24*14)

        return response