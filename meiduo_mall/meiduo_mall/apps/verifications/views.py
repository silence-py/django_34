from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection
from django import http
from random import randint
import logging

from meiduo_mall.utils.response_code import RETCODE
from meiduo_mall.libs.captcha.captcha import captcha
# from meiduo_mall.libs.yuntongxun.sms import CCP
from . import constants
from celery_tasks.sms.tasks import ccp_send_sms_code

logger = logging.getLogger('django')


class ImageCodeView(View):

    """
    def get(self, request, uuid):
        # 生成图片验证码
        # name: 标识验证码校验唯一值
        # text: 验证码的字符串数据
        # image = 验证码的二进制数据
        name, text, image = captcha.generate_captcha()

        # 连接数据库存储验证数据: uuid-->text
        redis_conn = get_redis_connection('verify_code')
        redis_conn.setex(uuid, 300, text)

        # 响应图片数据
        return http.HttpResponse(image, content_type="img/jpg")
    """

    def get(self, request, uuid):
        name, text, image = captcha.generate_captcha()

        redis_conn = get_redis_connection('verify_code')
        redis_conn.setex('img_%s' % uuid, constants.IMAGE_CODE_REDIS_EXPIRES, text)

        return http.HttpResponse(image, content_type='image/jpg')


class SMSCodeView(View):

    def get(self, request, mobile):
        # 1.获取查询参数
        query_dict = request.GET
        image_code = query_dict.get('image_code')
        uuid = query_dict.get('uuid')

        redis_conn = get_redis_connection('verify_code')

        # 判断是否频繁发送验证码
        sms_send_code = redis_conn.get('sms_send_%s' % mobile)
        if sms_send_code:
            return http.JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '访问过于频繁'})

        # 2.验证参数
        if all([image_code, uuid]) is False:
            return http.HttpResponseForbidden("缺少必要的参数")

        # 3.校验图片验证码
        image_code_server = redis_conn.get('img_'+uuid)

        # 判断图片验证码在数据库中是否为空(已经过期)
        if image_code_server is None:
            return http.JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码已过期'})

        # 对数据库中提取的数据进行解码
        image_str_server = image_code_server.decode()

        # 判断用户填写的短信验证码是否与数据库中的验证码匹配
        if image_str_server.lower() != image_code.lower():
            return http.JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码错误'})

        # 4.发送短信验证码
        sms_code = '%06d' % randint(0, 999999)
        logger.info(sms_code)

        # 实例化pipeline管道对象
        pl = redis_conn.pipeline()

        # 删除数据库中的图片验证码
        # redis_conn.delete('img_' + uuid)
        pl.delete('img_' + uuid)

        # 将短信验证码存储至数据库
        # redis_conn.setex('sms_%s' % mobile, contans.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex('sms_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)

        # 存储验证码标识(过期时间为60秒)
        # redis_conn.setex('sms_send_%s' % mobile, contans.SMS_CODE_FLAG_REDIS_EXPIRES, 1)
        pl.setex('sms_send_%s' % mobile, constants.SMS_CODE_FLAG_REDIS_EXPIRES//5, 1)

        pl.execute()

        # CCP().send_template_sms(手机号码, [验证码, 提示用户验证码多久过期], 指定短信模板)
        # CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES // 60], 1)

        # 使用celery分布式任务队列
        # ccp_send_sms_code(mobile, sms_code)   # 此调用方式依旧会进程阻塞
        ccp_send_sms_code.delay(mobile, sms_code)   # 此调用方式只会将函数引用存储至仓库中然后由worker执行

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})