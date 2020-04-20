from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseServerError
from django.views import View
from django.conf import settings
from carts.utils import merge_cart_cookie_to_redis
from django.contrib.auth import login
from django_redis import get_redis_connection
import re

from . import sinaweibopy3
from meiduo_mall.utils.response_code import RETCODE
from .models import OAuthSinaUser
from users.models import User
from oauth.utils import generate_openid_signature, check_openid

# Create your views here.


class SinaLoginURLView(View):
    def get(self, request):
        # 获取查询参数数据
        next_url = request.GET.get('next', '/')

        # 创建微博客户端对象
        client = sinaweibopy3.APIClient(app_key=settings.APP_KEY,   # APP_KEY
                                        app_secret=settings.APP_SECRET,   # APP_SECRET
                                        redirect_uri=settings.REDIRECT_URL)   # 回调地址

        # 生成跳转链接
        login_url = client.get_authorize_url()

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'login_url': login_url})


class SinaOauthView(View):
    def get(self, request):

        code = request.GET.get('code')

        # 校验数据
        if code is None:
            return HttpResponseForbidden('缺少必要参数')

        # 创建客户端对象
        client = sinaweibopy3.APIClient(app_key=settings.APP_KEY,   # APP_KEY
                                        app_secret=settings.APP_SECRET,   # APP_SECRET
                                        redirect_uri=settings.REDIRECT_URL)   # 回调地址
        try:
            result = client.request_access_token(code)
            access_token = result.access_token
            uid = result.uid
        except Exception as e:
            return HttpResponseServerError("oauth2.0认证失败")

        # 判断帐号是否已经绑定用户
        try:
            sina_user = OAuthSinaUser.objects.get(uid=uid)
        except OAuthSinaUser.DoesNotExist:
            # 未绑定用户渲染绑定用户页面
            data = {'uid': generate_openid_signature(uid)}
            return render(request, 'sina_callback.html', data)
        else:
            # 获取用户对象
            user = sina_user.user
            # 保持登录状态
            login(request, user)
            # 重定向到指定页面
            response = redirect('/')
            merge_cart_cookie_to_redis(request, response)
            response.set_cookie('username', user.username, max_age=3600*24*14)
            return response

    def post(self, request):
        # 获取数据
        query_dict = request.POST
        mobile = query_dict.get('mobile')
        password = query_dict.get('password')
        sms_code_client = query_dict.get('sms_code')
        openid = query_dict.get('uid')

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

        open_id = check_openid(openid)
        if open_id is None:
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

        OAuthSinaUser.objects.create(user=user, uid=open_id)

        # 状态保持
        login(request, user)

        # 重定向并设置cookie
        response = redirect('/')
        # 合并购物车
        merge_cart_cookie_to_redis(request, response)

        response.set_cookie('username', user.username, max_age=3600 * 24 * 14)

        return response