from django.shortcuts import render
from django.http import HttpResponseForbidden, JsonResponse
from alipay import AliPay
from django.conf import settings
import os

from meiduo_mall.utils.views import LoginRequiredView
from orders.models import OrderInfo
from meiduo_mall.utils.response_code import RETCODE
from .models import Payment

# 读取公私密钥
app_private_key_string = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/app_private_key.pem')).read()
alipay_public_key_string = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/alipay_public_key.pem')).read()


class PaymentURLView(LoginRequiredView):
    def get(self, request, order_id):
        # 校验数据
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'])
        except OrderInfo.DoesNotExist:
            return HttpResponseForbidden('订单提交失败')

        # 创建alipay对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,   # APPID
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,

            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )

        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 要支付的订单id
            total_amount=str(order.total_amount),  # 要支付的订单总金额 Decimal类型要转换为字符串格式
            subject='美多商城%s' % order_id,  # 主题
            return_url=settings.ALIPAY_RETURN_URL,  # 回调地址
        )
        # 拼接路径
        alipay_url = settings.ALIPAY_URL + order_string
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'alipay_url': alipay_url})


class PaymentSuccessView(LoginRequiredView):
    """订单支付成功"""
    def get(self, request):
        # 获取查询参数数据
        query_dict = request.GET
        data = query_dict.dict()
        sign = data.pop('sign')

        # 创建alipay对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,   # APPID
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,

            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )
        # 判断认证是否通过
        if alipay.verify(data, sign):
            order_id = data.get('out_trade_no')
            trade_id = data.get('trade_no')
            try:
                # 判断订单号和支付宝流水号是否已经存在
                Payment.objects.get(order_id=order_id, trade_id=trade_id)
            except Payment.DoesNotExist:

                # 订单支付通过创建支付宝流水号表格并关联订单号
                Payment.objects.create(
                    order_id=order_id,
                    trade_id=trade_id,
                )
                # 修改订单的支付状态
                OrderInfo.objects.filter(order_id=order_id, status=OrderInfo.ORDER_STATUS_ENUM['UNPAID']).update(
                    status=OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT'])

            # 渲染订单支付成功页面
            return render(request, 'pay_success.html', {'trade_id': trade_id})

        else:
            # 提前响应
            return HttpResponseForbidden('订单支付失败')

