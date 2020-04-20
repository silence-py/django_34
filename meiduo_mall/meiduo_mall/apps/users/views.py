from django.shortcuts import render, redirect
from django.views import View
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.db.utils import DatabaseError
from django_redis import get_redis_connection
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
# from django.core.mail import send_mail
from random import randint
import re, json, logging


from .models import User
from meiduo_mall.utils.response_code import RETCODE
from meiduo_mall.utils.views import LoginRequiredView
from celery_tasks.email.tasks import send_verify_email
from users.utils import generate_verify_email_url, check_email
from goods.models import SKU
from .models import Address
from oauth.utils import generate_openid_signature, check_openid
from carts.utils import merge_cart_cookie_to_redis
from verifications import constants
from celery_tasks.sms.tasks import ccp_send_sms_code


logger = logging.getLogger('django')


# Create your views here.
class RegisterView(View):
    """用户注册页面"""

    def get(self, request):
        return render(request, 'register.html')  # 返回注册页面

    def post(self, request):
        # 1.获取表单数据
        query_dict = request.POST
        username = query_dict.get('username')
        password = query_dict.get('password')
        password2 = query_dict.get('password2')
        sms_code_client = query_dict.get('sms_code')
        mobile = query_dict.get('mobile')
        allow = query_dict.get('allow')

        # 连接数据库
        redis_conn = get_redis_connection('verify_code')

        # 2. 校验数据
        if all([username, password, password2, sms_code_client, mobile, allow]) is False:
            return HttpResponseForbidden('数据填写不完整')

        if not re.match('^[a-zA-Z0-9_-]{5,20}$', username):
            return HttpResponseForbidden('请输入5-20个字符的用户名')
        if not re.match('^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseForbidden('请输入8-20位的密码')
        if password != password2:
            return HttpResponseForbidden('两次输入的密码不一致')
        if not re.match('^1[3-9]\d{9}$', mobile):
            return HttpResponseForbidden('请输入正确的手机号码')

        # 查询短信验证码
        sms_code_server = redis_conn.get('sms_%s' % mobile).decode()

        # 判断短信验证码是否已经过期
        if sms_code_server is None:
            return render(request, 'register.html', context={'sms_code_error': '短信验证码已过期'})

        # 验证短信验证码
        if sms_code_client != sms_code_server:
            return render(request, 'register.html', context={'sms_code_error': '短信验证码错误'})

        # 3.保存注册数据
        try:
            user = User.objects.create_user(username=username, password=password, mobile=mobile)
        except DatabaseError:
            return render(request, 'register.html', {'register_errmsg': '注册失败'})

        # 4.状态保持
        login(request, user)

        response = redirect('/')
        response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)

        return response


class UserNameCountView(View):
    """用户名重复检测"""

    def get(self, request, username):
        count = User.objects.filter(username=username).count()
        return JsonResponse(data={'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class MobileCountView(View):
    """手机号重复检测"""

    def get(self, request, mobile):
        count = User.objects.filter(mobile=mobile).count()
        return JsonResponse(data={'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class LoginView(View):
    """用户登录页面"""

    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        # 获取表单数据
        query_dict = request.POST
        username = query_dict.get('username')
        password = query_dict.get('pwd')
        remembered = query_dict.get('remembered')

        # 校验数据
        if all([username, password]) is None:
            return HttpResponseForbidden("缺少必要的参数")

        if not re.match('^[a-zA-Z0-9_-]{5,20}$', username):
            return render(request, 'login.html', {'loginerror': '帐号或密码错误'})

        if not re.match('^[0-9A-Za-z]{8,20}$', password):
            return render(request, 'login.html', {'loginerror': '帐号或密码错误'})


        # 多帐号登录功能实现
        # try:
        #     user = User.objects.get(username=username)
        # except User.DoesNotExist:
        #     try:
        #         user = User.objects.get(mobile=username)
        #     except User.DoesNotExist:
        #         return render(request, 'login.html', {'account_errmsg': '帐号或密码错误'})
        #
        # if user.check_password(password) is False:
        #     return render(request, 'login.html', {'account_errmsg': '帐号或密码错误'})

        # 用户认证    authenticate(请求对象, 认证参数), 查询不到用户返回None
        user = authenticate(request, username=username, password=password)
        if user is None:
            return render(request, 'login.html', {'loginerror': '帐号或密码错误'})

        # 状态保持
        login(request, user)
        if remembered is None:
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)

        # response = redirect('/')
        # 根据查询参数next的值重定向
        response = redirect(request.GET.get('next') or '/')

        merge_cart_cookie_to_redis(request, response)

        # 设置cookie
        response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE if remembered else None)

        return response


class LogoutView(View):
    """用户退出登录"""

    def get(self, request):
        logout(request)
        response = redirect('/login/')
        response.delete_cookie('username')
        return response


class InfoView(LoginRequiredMixin, View):

    def get(self, request):
        user = request.user
        # isinstance(对象, 类)  判断对象是否属于此类, 若属于返回True, 否则返回False
        # if isinstance(user, User):
        #     return render(request, 'user_center_info.html')
        # is_authenticated 判断用户是否登录, 返回一个对象
        # if user.is_authenticated:
        return render(request, 'user_center_info.html')
        # else:
        #     return redirect('/login/?next=/info/')


class EmailView(LoginRequiredView):

    def put(self, request):

        user = request.user
        if user.email == '':

            # 接收数据
            json_str = request.body.decode()
            data = json.loads(json_str)
            email = data.get('email')

            # 校验数据
            if email is None:
                return HttpResponseForbidden('缺少必要参数')

            if not re.match('^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return HttpResponseForbidden('邮箱不正确')

            # 修改数据
            user.email = email
            user.save()
        # 发送邮件
        # send_mail(subject='主题', message='基本内容', from_email='发件人', recipient_list='收件人列表',
        #           html_message='邮件超文本内容')
        # subject = '美多商城邮箱验证'
        # send_mail(subject=subject, message='', from_email=settings.EMAIL_FROM, recipient_list=[user.email],
        #           html_message='邮件超文本内容')

        # 对查询参数进行加密
        verify_url = generate_verify_email_url(user)
        # 使用celery发送邮件
        send_verify_email.delay(user.email, verify_url)

        # 响应
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class VerifyEmailView(View):

    def get(self, request):
        # 获取数据
        data = request.GET.get('token')

        if data is None:
            return HttpResponseForbidden('缺少必要的参数')

        token_dict = check_email(data)

        # 校验数据
        user_id = token_dict.get('user_id')
        email = token_dict.get('email')

        # 修改邮箱激活状态
        try:
            user = User.objects.get(id=user_id, email=email)

        except User.DoesNotExist:
            return HttpResponseForbidden('验证失败')

        else:
            try:
                user.email_active = True
                user.save()
            except Exception as e:
                return HttpResponseForbidden('邮箱激活失败')

        # 响应页面
        return redirect('/info/')


class AddressView(LoginRequiredView):

    def get(self, request):
        # 获取当前用户
        user = request.user
        # 查询当前用户的所有收获地址
        query_set = Address.objects.filter(user=user, is_deleted=False)
        # query_sets = user.addresses.filter(is_deleted=False)
        # 将查询集对象转换为列表
        address_list = []
        for address in query_set:
            address_list.append(
                {
                    'id': address.id,
                    'title': address.title,
                    'receiver': address.receiver,
                    'province_id': address.province.id,
                    'province': address.province.name,
                    'city_id': address.city.id,
                    'city': address.city.name,
                    'district_id': address.district.id,
                    'district': address.district.name,
                    'place': address.place,
                    'mobile': address.mobile,
                    'tel': address.tel,
                    'email': address.email,
                }
            )
        # 编辑模板内容
        content = {
            'addresses': address_list,
            'default_address_id': user.default_address_id
        }
        return render(request, 'user_center_site.html', content)


class CreateAddressView(LoginRequiredView):

    def post(self, request):

        user = request.user
        count = user.addresses.filter(is_deleted=False).count()
        if count == 20:
            return JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '添加地址已上限'})

        user = request.user
        # 接收
        json_data = json.loads(request.body.decode())
        # 校验
        title = json_data.get('title')
        receiver = json_data.get('receiver')
        province_id = json_data.get('province_id')
        city_id = json_data.get('city_id')
        district_id = json_data.get('district_id')
        place = json_data.get('place')
        mobile = json_data.get('mobile')
        tel = json_data.get('tel')
        email = json_data.get('email')

        if all([title, receiver, province_id, city_id, district_id, place, mobile]) is False:
            return HttpResponseForbidden('缺少必要的参数')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseForbidden('格式错误')

        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return HttpResponseForbidden('参数tel有误')

        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return HttpResponseForbidden('参数email有误')

        try:
            # 新增收获地址
            address = Address.objects.create(user=request.user,
                                             title=receiver,
                                             receiver=receiver,
                                             province_id=province_id,
                                             city_id=city_id,
                                             district_id=district_id,
                                             place=place,
                                             mobile=mobile,
                                             tel=tel,
                                             email=email
                                             )
            # 判断用户是否有默认地址
            if not user.default_address:
                user.default_address = address
                user.save()

        except Exception as e:
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '新增地址失败'})

        # 数据转字典格式
        data = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province_id': address.province.id,
            'province': address.province.name,
            'city_id': address.city.id,
            'city': address.city.name,
            'district_id': address.district.id,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email,
        }

        # 响应
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'address': data})


class DeleteAddressView(LoginRequiredView):

    def delete(self, request, id):
        """删除收货地址"""
        # 接收
        address_id = id

        # 校验
        if not address_id:
            return HttpResponseForbidden('缺少必要参数')

        # 逻辑删除
        try:
            address = Address.objects.get(id=address_id)
            address.is_deleted = True
            address.save()

        except Address.DoesNotExist:
            return HttpResponseForbidden('地址不存在')

        # 响应

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

    def put(self, request, id):
        """编辑收货地址"""
        # 接收
        address_id = int(id)
        user = request.user
        json_data = json.loads(request.body.decode())
        # 校验
        if not address_id:
            return HttpResponseForbidden('缺少必要参数')
        title = json_data.get('title')
        receiver = json_data.get('receiver')
        province_id = json_data.get('province_id')
        city_id = json_data.get('city_id')
        district_id = json_data.get('district_id')
        place = json_data.get('place')
        mobile = json_data.get('mobile')
        tel = json_data.get('tel')
        email = json_data.get('email')

        if all([title, receiver, province_id, city_id, district_id, place, mobile]) is False:
            return HttpResponseForbidden('缺少必要的参数')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseForbidden('格式错误')

        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return HttpResponseForbidden('参数tel有误')

        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return HttpResponseForbidden('参数email有误')
        try:
            address = Address.objects.get(id=address_id)
            address.is_deleted = True
            address.save()
        except Address.DoesNotExist:
            return HttpResponseForbidden('地址不存在')
        try:
            # 新增收获地址
            address = Address.objects.create(user=request.user,
                                             title=receiver,
                                             receiver=receiver,
                                             province_id=province_id,
                                             city_id=city_id,
                                             district_id=district_id,
                                             place=place,
                                             mobile=mobile,
                                             tel=tel,
                                             email=email
                                             )
            # 判断用户是否有默认地址
            # if not user.default_address:
            #     user.default_address = address
            #     user.save()

            if user.default_address_id == address_id:
                user.default_address_id = address.id
                user.save()

        except Exception as e:
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '新增地址失败'})

        # 数据转字典格式
        data = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province_id': address.province.id,
            'province': address.province.name,
            'city_id': address.city.id,
            'city': address.city.name,
            'district_id': address.district.id,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email,
        }

        # 响应
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'address': data})


class DefaultAddressView(LoginRequiredView):
    def put(self, request, id):

        # 接收
        address_id = id
        user = request.user

        # 校验
        if not address_id:
            return HttpResponseForbidden('缺少必要参数')

        # 修改
        try:
            user.default_address_id = address_id
            user.save()
        except User.DoesNotExist:
            return HttpResponseForbidden('用户不存在')
        # 响应

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class AddressTitleView(LoginRequiredView):

    def put(self, request, id):
        # 接收
        address_id = id
        data = json.loads(request.body.decode())
        title = data.get('title')

        # 校验
        if not all([address_id, data, title]):
            return HttpResponseForbidden('缺少必要参数')

        # 修改
        try:
            address = Address.objects.get(id=address_id)
            address.title = title
            address.save()
        except Address.DoesNotExist:
            return HttpResponseForbidden('地址不存在')

        return JsonResponse({'code': RETCODE.OK, 'errmsg': '修改标题成功'})


class PasswordView(LoginRequiredView):

    def get(self, request):
        """渲染用户修改密码页面"""

        return render(request, 'user_center_pass.html')

    def post(self, request):
        # 接收数据
        user = request.user
        data = request.POST
        old_pwd = data.get('old_pwd')
        new_pwd = data.get('new_pwd')
        new_cpwd = data.get('new_cpwd')

        # 校验数据
        if all([old_pwd, new_pwd, new_cpwd]) is False:
            return HttpResponseForbidden('缺少必要参数')

        if new_pwd != new_cpwd:
            return HttpResponseForbidden('密码不一致')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', old_pwd):
            return HttpResponseForbidden('密码格式错误')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', new_pwd):
            return HttpResponseForbidden('密码格式错误')

        if not user.check_password(old_pwd):
            return render(request, 'user_center_pass.html', {'change_pwd_errmsg': "密码错误"})

        # 修改密码
        try:
            user.set_password(new_pwd)
            user.save()
        except User.DoesNotExist:
            return HttpResponseForbidden('用户不存在')

        # 用户退出登录
        logout(request)

        # 重定向到用户登录界面
        response = redirect('/login/')
        response.delete_cookie('username')
        return response


class UserBrowserHistory(View):

    def post(self, request):
        """用户历史浏览商品"""

        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'code': RETCODE.SESSIONERR, 'errmsg': '用户未登录'})

        # 接收数据
        json_data = request.body.decode()
        json_dict = json.loads(json_data)
        sku_id = json_dict.get('sku_id')
        user_id = request.user.id

        # 校验数据
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return render(request, '404.html')

        # 连接数据库
        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()

        # 去重复
        pl.lrem(user_id, 0, sku_id)

        # 从头插入
        pl.lpush(user_id, sku_id)

        # 切片取出
        pl.ltrim(user_id, 0, 4)

        pl.execute()

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

    def get(self, request):
        """渲染用户中心浏览历史"""
        user = request.user

        redis_conn = get_redis_connection('history')

        # 查询当前用户的浏览记录
        sku_ids = redis_conn.lrange(user.id, 0, -1)

        sku_list = []

        for sku_id in sku_ids:

            sku = SKU.objects.get(id=sku_id)

            sku_list.append({
                'id': sku.id,
                'name': sku.name,
                'price': sku.price,
                "default_image_url": sku.default_image.url,
            })

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'skus': sku_list})


class FindPasswordView(View):
    """找回用户密码"""
    def get(self, request):
        return render(request, 'find_password.html')


class ImageToFindPasswordView(View):
    """找回密码之校验图片验证码"""
    def get(self, request, username):
        # 接收数据
        username = username
        query_dict = request.GET
        image_code = query_dict.get('image_code')
        uuid = query_dict.get('uuid')

        # 校验数据
        if all({username, image_code, uuid}) is False:
            return HttpResponseForbidden('缺少必要参数')

        if not re.match(r'[a-zA-Z0-9_-]{5,20}', username):
            return HttpResponseForbidden('参数有误')

        # 判断用户是否存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(mobile=username)
            except User.DoesNotExist:
                return JsonResponse({'code': RETCODE.USERERR, 'errmsg': '用户名或手机号不存在'},
                                    status=constants.USER_MOBILE_ERROR)

        redis_conn = get_redis_connection('verify_code')
        image_text = redis_conn.get('img_%s' % uuid)
        # 判断图片验证码在数据库中是否为空(是否过期)
        if image_text is None:
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码已过期'},
                                status=constants.VERIFY_CODE_ERROR)

        # # 删除图片验证码
        # redis_conn.delete('img_%s' % uuid)

        # 判断图片验证码是否正确
        if image_code.upper() != image_text.decode().upper():
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图形验证码错误'},
                                status=constants.VERIFY_CODE_ERROR)

        # 将token存储到redis数据库
        redis_conn.setex('token_%s' % user.mobile, constants.ACCESS_TOKEN__REDIS_EXPIRES, user.username)

        # 加密用户手机号
        access_token = generate_openid_signature(user.mobile)

        # 响应结果
        return JsonResponse({'status': RETCODE.OK, 'errmsg': 'OK', 'mobile': user.mobile, 'access_token': access_token})


class SmsCodeToFindPasswordView(View):
    """找回密码之发送短信验证码"""
    def get(self, request):
        # 接收数据
        access_token = request.GET.get('access_token')
        mobile = check_openid(access_token)

        # 链接redis数据库校验token
        redis_conn = get_redis_connection('verify_code')
        username = redis_conn.get('token_%s' % mobile)

        # 判断是否频繁发送验证码
        sms_send_code = redis_conn.get('sms_send_%s' % mobile)
        if sms_send_code:
            return JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '访问过于频繁', 'message': '访问过于频繁'},
                                status=constants.VERIFY_CODE_ERROR)

        # 校验token是否过期
        if not username:
            return JsonResponse({'code': RETCODE.NODATAERR, 'errmsg': '等待超时', 'message': '等待超时,请刷新页面'},
                                status=constants.VERIFY_CODE_ERROR)

        # 校验用户是否存在
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            return HttpResponseForbidden('用户不存在')

        # 发送短信验证码
        sms_code = '%06d' % randint(0, 999999)
        logger.info(sms_code)

        # 实例化pipeline管道对象
        pl = redis_conn.pipeline()

        # 将短信验证码存储至数据库
        # redis_conn.setex('sms_%s' % mobile, contans.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex('sms_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)

        # 存储验证码标识(过期时间为60秒)
        # redis_conn.setex('sms_send_%s' % mobile, contans.SMS_CODE_FLAG_REDIS_EXPIRES, 1)
        pl.setex('sms_send_%s' % mobile, constants.SMS_CODE_FLAG_REDIS_EXPIRES // 5, 1)

        # 执行管道
        pl.execute()

        # 使用celery分布式任务队列
        # ccp_send_sms_code(mobile, sms_code)   # 此调用方式依旧会进程阻塞
        ccp_send_sms_code.delay(mobile, sms_code)  # 此调用方式只会将函数引用存储至仓库中然后由worker执行

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class CheckSmsToFindPasswordView(View):
    """找回密码之校验短信验证码"""
    def get(self, request, username):

        # 接收数据
        # 用户名
        username = username
        # 短信验证码(客户端)
        sms_code_cli = request.GET.get('sms_code')

        # 判断用户是否存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(mobile=username)
            except User.DoesNotExist:
                return JsonResponse({'code': RETCODE.USERERR, 'errmsg': '用户名或手机号不存在'},
                                    status=constants.USER_MOBILE_ERROR)
        # 获取用户手机号
        mobile = user.mobile
        # 连接redis数据库校验短信验证码
        redis_conn = get_redis_connection('verify_code')

        # 获取redis中的短信验证码数据
        sms_code_server = redis_conn.get('sms_%s' % mobile)

        # # # 判断短信验证码是否过期
        if not sms_code_server:
            return JsonResponse({'code': RETCODE.NODATAERR, 'errmsg': '请输入正确的短信验证码',},
                                status=constants.VERIFY_CODE_ERROR)

        # # 判断短信验证码是否正确
        if sms_code_cli != sms_code_server.decode():
            return JsonResponse({'code': RETCODE.SMSCODERR, 'errmsg': '短信验证码不正确'},
                                status=constants.VERIFY_CODE_ERROR)

        # 设置access_token
        access_token = generate_openid_signature(user.mobile)

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'user_id': user.id, 'access_token': access_token})


class SetNewPasswordView(View):
    """设置新密码"""
    def post(self, request, user_id):

        # 接收数据
        json_data = json.loads(request.body.decode())
        user_id = user_id
        password = json_data.get('password')
        password2 = json_data.get('password2')
        access_token = json_data.get('access_token')
        mobile = check_openid(access_token)
        # 校验数据
        if all([user_id, password, password2, access_token]) is False:
            return HttpResponseForbidden('缺少必要参数')

        # 判断用户是否存在
        try:
            user = User.objects.get(id=user_id, mobile=mobile)
        except User.DoesNotExist:
            return HttpResponseForbidden('用户校验失败')

        if password != password2:
            return JsonResponse({'code': RETCODE.PWDERR, 'errmsg': '两次密码不一致', 'message': '短信验证码已过期'},
                                status=constants.VERIFY_CODE_ERROR)

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return JsonResponse({'code': RETCODE.PWDERR, 'errmsg': '密码格式有误', 'message': '密码格式有误'},
                                status=constants.VERIFY_CODE_ERROR)

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password2):
            return JsonResponse({'code': RETCODE.PWDERR, 'errmsg': '密码格式有误', 'message': '密码格式有误'},
                                status=constants.VERIFY_CODE_ERROR)

        # 修改用户密码
        user.set_password(password)
        user.save()

        return JsonResponse({'code': RETCODE.OK, 'errmsg': '修改密码成功'})

