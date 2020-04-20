from django.shortcuts import render
from decimal import Decimal
from django_redis import get_redis_connection
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.core.paginator import Paginator,EmptyPage
import json, logging
from django.utils import timezone

from meiduo_mall.utils.views import LoginRequiredView
from meiduo_mall.utils.response_code import RETCODE
from users.models import Address
from goods.models import SKU
from .models import OrderInfo, OrderGoods

logger = logging.getLogger('django')


# Create your views here.
class OrderSettlementView(LoginRequiredView):
    """订单结算页面"""
    def get(self, request):
        user = request.user
        # 查询当前用户下的所有收货地址
        address_qs = Address.objects.filter(user=user, is_deleted=False)

        # 查询当前用户已勾选的sku商品
        redis_cli = get_redis_connection('carts')
        # {sku_id: count}
        hash_cart = redis_cli.hgetall('cart_%s' % user.id)
        set_cart = redis_cli.smembers('selected_%s' % user.id)
        sku_dict = {}
        # 过滤已勾选的商品并包装成{sku_id: count}
        for sku_id_byte in set_cart:
            sku_dict[int(sku_id_byte)] = int(hash_cart[sku_id_byte])

        # 获取所有sku对象查询集
        sku_qs = SKU.objects.filter(id__in=sku_dict.keys())
        # 设置初始总量0
        total_count = 0
        # 设置初始总价0.00
        total_amount = Decimal('0.00')
        # 获取所有sku对象
        for sku in sku_qs:
            sku.count = sku_dict[sku.id]
            sku.amount = sku.count * sku.price
            total_count += sku.count
            total_amount += sku.amount
        # 设置固定运费
        freight = Decimal('10.00')

        context = {
            'addresses': address_qs,
            'skus': sku_qs,
            'total_count': total_count,
            'total_amount': total_amount,
            'freight': freight,
            'payment_amount': total_amount + freight,
        }

        return render(request, 'place_order.html', context)


class OrderCommitView(LoginRequiredView):
    """订单提交页面"""
    def post(self, request):
        # 接收数据
        user = request.user
        json_data = json.loads(request.body.decode())
        address_id = json_data.get('address_id')
        pay_method = json_data.get('pay_method')

        # 校验数据
        if all([address_id, pay_method]) is False:
            return HttpResponseForbidden('缺少必要的参数')

        try:
            address = Address.objects.get(id=address_id, user=user, is_deleted=False)
        except Address.DoesNotExist:
            return HttpResponseForbidden('收货地址有误')

        if pay_method not in (OrderInfo.PAY_METHODS_ENUM['CASH'], OrderInfo.PAY_METHODS_ENUM['ALIPAY']):
            return HttpResponseForbidden('支付方式有误')
        # 修改四表数据   order_info, order_goods, sku, spu

        # 生成订单ID
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + '%09d' % user.id

        # 判断订单状态
        status = OrderInfo.ORDER_STATUS_ENUM['UNPAID'] if pay_method == OrderInfo.PAY_METHODS_ENUM['ALIPAY'] else OrderInfo.ORDER_STATUS_ENUM['UNSEND']

        # 开始事务
        with transaction.atomic():
            # 创建保存点
            save_point = transaction.savepoint()
            try:
                # 暴力回滚
                # 创建订单信息表
                order_info = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=0,
                    total_amount=Decimal('0.00'),
                    freight=Decimal('10.00'),
                    pay_method=pay_method,
                    status=status,
                )

                # 修改sku的库存和销量以及spu的销量
                redis_cli = get_redis_connection('carts')
                count_hash = redis_cli.hgetall('cart_%s' % user.id)
                selected_set = redis_cli.smembers('selected_%s' % user.id)
                cart_dict = {}
                # 过滤数据   已勾选商品{sku_id: count}
                for sku_id in selected_set:
                    cart_dict[int(sku_id)] = int(count_hash[sku_id])

                for sku_id in cart_dict:
                    while True:
                        sku = SKU.objects.get(id=sku_id)

                        # 原始库存和销量
                        origin_stock = sku.stock
                        origin_sales = sku.sales

                        # 购买数量
                        buy_count = cart_dict[sku_id]

                        # 判断库存是否充足
                        if origin_stock < buy_count:
                            # 如果执行到此处回滚数据至保存点
                            transaction.savepoint_rollback(save_point)
                            return JsonResponse({'code': RETCODE.STOCKERR, 'errmsg': '%s商品库存不足' % sku.name})

                        # 购买后的库存和销量
                        new_stock = origin_stock - buy_count
                        new_sales = origin_sales + buy_count

                        # 更新sku的库存和销量
                        # sku.stock = new_stock
                        # sku.sales = new_sales
                        # sku.save()
                        result = SKU.objects.filter(id=sku_id, stock=origin_stock).update(sales=new_sales, stock=new_stock)
                        if result == 0:
                            continue

                        # 更新spu的销量
                        spu = sku.spu
                        spu.sales += buy_count
                        spu.save()

                        # 创建商品信息表
                        order_goods = OrderGoods.objects.create(
                            order=order_info,
                            sku=sku,
                            count=buy_count,
                            price=sku.price,
                        )
                        order_info.total_count += buy_count
                        order_info.total_amount += buy_count * sku.price
                        break

                # 订单总金额包含运费
                order_info.total_amount += order_info.freight
                order_info.save()
            except Exception as e:
                logger.error(e)
                transaction.savepoint_rollback(save_point)
                return JsonResponse({'code': RETCODE.STOCKERR, 'errmsg': '订单提交失败'})
            else:
                # 提交事务
                transaction.savepoint_commit(save_point)

        # 清空购物车数据
        pl = redis_cli.pipeline()
        pl.hdel('cart_%s' % user.id, *selected_set)
        pl.delete('selected_%s' % user.id)
        pl.execute()

        # 响应json
        return JsonResponse({'code': RETCODE.OK, 'errmsg': '订单提交成功', 'order_id': order_id})


class OrderSuccessView(LoginRequiredView):
    """订单提交成功界面"""
    def get(self, request):
        # 接收
        user = request.user
        result = request.GET
        order_id = result.get('order_id')
        payment_amount = result.get('payment_amount')
        pay_method = result.get('pay_method')

        # 校验
        if all([order_id, pay_method, payment_amount]) is False:
            return HttpResponseForbidden('缺少必要参数')

        try:
            OrderInfo.objects.get(order_id=order_id, pay_method=pay_method, total_amount=payment_amount, user=user)
        except OrderInfo.DoesNotExist:
            return HttpResponseForbidden('订单提交失败')

        # 响应
        context = {
            'payment_amount': payment_amount,
            'order_id': order_id,
            'pay_method': pay_method
        }

        return render(request, 'order_success.html', context)


class ShowOrderView(LoginRequiredView):
    """展示用户订单"""
    def get(self, request, page):
        # 获取当前登录用户
        user = request.user

        # 如果没有指定页面默认为第一页
        page_num = page if page else 1

        # 查询所有的订单按最新创建时间降序排列
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 将所有订单分页展示, 每页显示数量为5个
        paginator = Paginator(orders, 5)

        try:
            # 获取指定页面显示的订单
            page_orders = paginator.page(page_num)
        except EmptyPage:
            return HttpResponseForbidden("EmptyPage")

        # 获取分页显示的每个订单对象
        for order in page_orders:

            # 获取支付方式的中文字段
            if order.pay_method == OrderInfo.PAY_METHODS_ENUM['ALIPAY']:
                order.pay_method_name = "支付宝"
            else:
                order.pay_method_name = '货到付款'

            # 获取订单状态的中文字段
            if order.status == OrderInfo.ORDER_STATUS_ENUM['UNPAID']:
                order.status_name = "待支付"
            elif order.status == OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT']:
                order.status_name = "待评价"
            elif order.status == OrderInfo.ORDER_STATUS_ENUM['UNSEND']:
                order.status_name = "待发货"
            elif order.status == OrderInfo.ORDER_STATUS_ENUM['UNRECEIVED']:
                order.status_name = "待收货"
            elif order.status == OrderInfo.ORDER_STATUS_ENUM['FINISHED']:
                order.status_name = "已完成"
            else:
                order.status_name = "已取消"

            # 单个订单添加一个列表属性
            order.sku_list = []
            # 查询每个订单对应的所有商品
            order_goods = OrderGoods.objects.filter(order_id=order.order_id)

            # 获取单个商品订单信息
            for goods in order_goods:
                sku = goods.sku
                sku.count = goods.count
                sku.amount = goods.count*goods.price
                order.sku_list.append(sku)

        # 获取总页数
        total_page = paginator.num_pages

        context = {
            'page_orders': page_orders,
            'page_num': page_num,
            'total_page': total_page,

        }

        return render(request, 'user_center_order.html', context)


class OrderCommentView(LoginRequiredView):
    """订单评价页面"""
    def get(self, request):

        # 接收数据
        user = request.user
        order_id = request.GET.get('order_id')

        # 校验数据
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, status=OrderInfo.ORDER_STATUS_ENUM["UNCOMMENT"])
        except OrderInfo.DoesNotExist:
            return HttpResponseForbidden('订单有误')

        # 查询到当前订单内的所有商品sku并包装成字典格式添加到列表中
        uncomment_goods_list = []
        order_goods = order.skus.filter(is_commented=False)
        for order_good in order_goods:
            sku = order_good.sku
            uncomment_goods_list.append({
                'sku_id': sku.id,
                'name': sku.name,
                'price': str(sku.price),
                'order_id': order_id,
                'default_image_url': sku.default_image.url
                # 'display_score': sku.display_score,
                # 'url': sku.url,
            })

        context = {
            'uncomment_goods_list': uncomment_goods_list
        }

        return render(request, 'goods_judge.html', context)

    def post(self, request):
        # 接收数据
        user = request.user
        data = json.loads(request.body.decode())
        order_id = data.get('order_id')
        sku_id = data.get('sku_id')
        comment = data.get('comment')   # 评论内容
        score = data.get('score')   # 商品评分
        is_anonymous = data.get('is_anonymous')   # 是否匿名

        # 校验数据
        if all([order_id, sku_id, comment, score]) is False:
            return HttpResponseForbidden('缺少必要的参数')

        try:
            # 判断订单号是否存在
            order = OrderInfo.objects.get(order_id=order_id, user=user, status=OrderInfo.ORDER_STATUS_ENUM["UNCOMMENT"])
        except OrderInfo.DoesNotExist:
            return HttpResponseForbidden('评价失败')

        try:
            # 判断商品是否存在
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('评价失败')

        # 校验商品评分是否为0-5的整数
        if score not in range(0, 6):
            return HttpResponseForbidden('请选择评价星级')

        # 判断is_anonymous是否为bool类型
        if isinstance(is_anonymous, bool) is False:
            return HttpResponseForbidden('评价失败')

        try:
            # 获取要评价的订单商品
            order_goods = OrderGoods.objects.get(sku=sku, order=order, is_commented=False)
        except OrderGoods.DoesNotExist:
            return HttpResponseForbidden('评价失败')
        else:
            # 修改并保存订单评价信息
            order_goods.comment = comment
            order_goods.score = score
            order_goods.is_anonymous = is_anonymous
            order_goods.is_commented = True
            order_goods.save()

        # 查询订单中所有商品类型总数
        order_sku_count = order.skus.count()

        # 查询订单中所有已评价商品类型总数
        count = order.skus.filter(is_commented=True).count()

        if order_sku_count == count:
            # 如果订单中所有商品已评价修改订单状态
            order.status = OrderInfo.ORDER_STATUS_ENUM['FINISHED']
            order.save()
            return JsonResponse({'code': RETCODE.OK, 'errmsg': '订单评价成功'})
        else:
            # 如果订单中商品未评价完刷新页面
            return JsonResponse({'code': RETCODE.REFRESH, 'errmsg': '订单评价成功'})