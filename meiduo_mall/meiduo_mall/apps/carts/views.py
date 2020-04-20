from django.shortcuts import render
from django.views import View
from django.http import HttpResponseForbidden, JsonResponse
import json, pickle, base64
from django_redis import get_redis_connection
import logging
from meiduo_mall.utils.response_code import RETCODE

from goods.models import SKU

logger = logging.getLogger('django')


# Create your views here.
class CartView(View):
    """购物车视图"""
    def post(self, request):
        """添加商品到购物车"""
        # 接收数据
        dict = json.loads(request.body.decode())
        sku_id = dict.get('sku_id')
        count = dict.get('count')
        selected = dict.get('selected', True)

        # 校验数据
        if all({sku_id, count}) is False:
            return HttpResponseForbidden('缺少必要参数')

        # 查询sku_id是否存在
        try:
            sku = SKU.objects.get(id=sku_id, is_launched=True)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('参数错误')

        # 判断count是否为整数类型
        try:
            count = int(count)
        except Exception as e:
            logger.error('count类型错误')
            return HttpResponseForbidden('count类型错误')

        # 判断selected是否为布尔类型
        if isinstance(selected, bool) is False:
            logger.error('selected类型错误')
            return HttpResponseForbidden('selected类型错误')

        user = request.user
        # 判断用户是否登录
        if user.is_authenticated:
            # 登录用户连接redis数据库
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()

            # 存储hash
            pl.hincrby('cart_%s' % user.id, sku_id, count)

            # 存储set
            if selected:
                pl.sadd('selected_%s' % user.id, sku_id)
            pl.execute()

            response = JsonResponse({"code": RETCODE.OK, "errmsg": '添加购物车成功'})

            # 响应
            return response


        else:
            """
            carts:{
                sku_id: {'count': 1, 'selected': True}
            }
            """
            # 未登录用户判断是否添加过购物车
            data = request.COOKIES.get('carts')
            if data:
                # 已添加用户获取购物车数据进行累加

                data_bytes = data.encode()
                data_bytes_unicode = base64.b64decode(data_bytes)
                carts_dict = pickle.loads(data_bytes_unicode)
                # 判断sku_id是否已经存在
                if sku_id in carts_dict:
                    origin_count = carts_dict[sku_id]['count']
                    count += origin_count
            else:
                # 首次添加用户新建列表
                carts_dict = {}

            carts_dict[sku_id] = {'count': count, 'selected': selected}
            # 将将字典转换为字符串数据
            data_bytes_unicode = pickle.dumps(carts_dict)
            data_bytes = base64.b64encode(data_bytes_unicode)
            data_str = data_bytes.decode()
            # 设置cookie
            response = JsonResponse({'code': RETCODE.OK, 'errmsg': '添加购物车成功'})
            response.set_cookie('carts', data_str, max_age=None)
            # 响应
            return response

    def get(self, request):
        """购物车展示"""

        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:

            # 登录用户查询数据并包装成cookie中的字典格式
            redis_conn = get_redis_connection('carts')

            # {sku_id:count, sku_id:count, sku_id:count}
            hash_result = redis_conn.hgetall('cart_%s' % user.id)
            if not hash_result:
                return render(request, 'cart.html')

            # {sku_id, sku_id, sku_id}
            set_result = redis_conn.smembers('selected_%s' % user.id)
            cart_dict ={}
            for sku_id_byte in hash_result:
                cart_dict[int(sku_id_byte)] = {'count': int(hash_result[sku_id_byte]), 'selected': sku_id_byte in set_result}

        else:
            # 未登录用户将数据转换成字典格式
            data_str = request.COOKIES.get('carts')
            # 如果有值转换为字典格式
            if data_str:
                cart_dict = pickle.loads(base64.b64decode(data_str.encode()))
            else:
                return render(request, 'cart.html')

        # 遍历字典中的sku_id进行查询,并包装成字典追加到列表中
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())
        context = []
        for sku in sku_qs:
            count = cart_dict[sku.id]['count']
            context.append({
                'id': sku.id,
                'selected': str(cart_dict[sku.id]['selected']),
                'default_image_url': sku.default_image.url,
                'name': sku.name,
                'price': str(sku.price),
                'count': count,
                'amount': str(sku.price * count),

            })

        return render(request, 'cart.html', {'cart_skus': context})

    def put(self, request):
        """修改购物车数据"""

        # 接收数据
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected', True)

        # 校验数据
        if all({sku_id, count}) is False:
            return HttpResponseForbidden('缺少必要参数')

        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('参数有误')

        try:
            count = int(count)
        except Exception as e:
            logger.error('count类型错误')
            return HttpResponseForbidden('count类型错误')

        if not isinstance(selected, bool):
            logger.error('selected类型错误')
            return HttpResponseForbidden('selected类型错误')

        # 判断用户是登录
        user = request.user
        if user.is_authenticated:
            redis_cli = get_redis_connection('carts')
            pl = redis_cli.pipeline()
            pl.hset('cart_%s' % user.id, sku_id, count)
            if selected:
                pl.sadd('selected_%s'% user.id, sku_id)
            else:
                pl.srem('selected_%s'% user.id, sku_id)

            pl.execute()
            context = {
                'id': sku.id,
                'selected': selected,
                'default_image_url': sku.default_image.url,
                'name': sku.name,
                'price': sku.price,
                'count': count,
                'amount': sku.price * count,
            }
            return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_sku': context})

        else:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                return HttpResponseForbidden('购物车为空')
            context = {
                'id': sku.id,
                'selected': selected,
                'default_image_url': sku.default_image.url,
                'name': sku.name,
                'price': sku.price,
                'count': count,
                'amount': sku.price * count,
            }
            cart_dict[sku_id] = {'count': count, 'selected': selected}
            cart_dict = base64.b64encode(pickle.dumps(cart_dict)).decode()
            response = JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_sku': context})
            response.set_cookie('carts', cart_dict)
            return response

    def delete(self, request):
        """删除购物车数据"""
        # 接收数据
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 校验数据
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('参数有误')

        response = JsonResponse({'code': RETCODE.OK, 'errmsg': '删除购物车成功'})
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # 登录用户链接redis数据库
            # hash = {sku_id: count}   set = {sku_id}
            redis_cli = get_redis_connection('carts')
            pl = redis_cli.pipeline()
            pl.hdel('cart_%s' % user.id, sku_id)
            pl.srem('selected_%s' % user.id, sku_id)
            pl.execute()
        else:
            # 未登录用户
            # 获取cart_str
            cart_str = request.COOKIES.get('carts')
            # 判断是否有值
            if cart_str:
                # 如果有值 cart_str--->cart_dict
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                # 如果没值 提前响应
                return response
            # 判断sku_id是否在cart_dict中, 防止报错
            # 删除cookie中对应sku_id数据
            if sku_id in cart_dict:
                del cart_dict[sku_id]
            # 如果为最后一条数据, 直接删除整条数据并提前响应
            if not cart_dict:
                response.delete_cookie('carts')
                return response
            # 将cart_dict--->cart_str
            cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            # 设置cookies
            response.set_cookie('carts', cart_str)

        return response


class CartSelectedAllView(View):
    def put(self, request):
        """购物车全选"""

        # 接收数据
        json_dict = json.loads(request.body.decode())
        selected = json_dict.get('selected')
        # 校验数据
        if not isinstance(selected, bool):
            return HttpResponseForbidden('selected类型错误')

        response = JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})
        # 判断用户登录
        user = request.user
        if user.is_authenticated:
            # 登录用户
            # 链接数据库
            # {sku_id: count}  {sku_id}
            redis_cli = get_redis_connection('carts')
            sku_dict = redis_cli.hgetall('cart_%s' % user.id)
            if selected:
                # 全选状态将hash中的所有sku_id添加到set集合中
                redis_cli.sadd('selected_%s' % user.id, *sku_dict.keys())
            else:
                # 取消全选将set集合中的所有sku_id删除
                redis_cli.delete('selected_%s' % user.id)
        else:
            # 未登录用户
            # 获取cart_str
            cart_str = request.COOKIES.get('carts')
            # 判断cart_str
            if cart_str:
                # 有值cart_str--->cart_dict
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                # 没有值进行提前响应
                return HttpResponseForbidden('购物车数据为空')
            # 批量修改selected的值
            for sku_dict in cart_dict.values():
                sku_dict['selected'] = selected
            # 转换类型cart_dict--->cart_str
            cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            # 设置cookie
            response.set_cookie('carts', cart_str)
        return response


class CartSimpleView(View):
    """简单版购物车"""
    def get(self, request):
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # hash {sku_id: count} set{sku_id}
            # 登录用户转换数据格式为{sku_id:{'count':1, 'selected': True}}
            redis_cli = get_redis_connection('carts')
            cart_hash = redis_cli.hgetall('cart_%s' % user.id)
            if not cart_hash:
                return JsonResponse({'code':RETCODE.NODATAERR, 'errmsg': '购物车无数据'})
            cart_set = redis_cli.smembers('selected_%s' % user.id)
            cart_dict = {}
            for sku_id_byte in cart_hash:
                cart_dict[int(sku_id_byte)] = {'count': int(cart_hash[sku_id_byte]), 'selected': sku_id_byte in cart_set}

        else:
            # 未登录用户获取cookie数据
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                # 获取到进行数据合适转换
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                # 获取不到提前响应
                return JsonResponse({'code':RETCODE.NODATAERR, 'errmsg': '购物车无数据'})

        context = []
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())
        for sku in sku_qs:
            count = cart_dict[sku.id]['count']
            context.append({
                'id': sku.id,
                'name': sku.name,
                'count': count,
                'default_image_url': sku.default_image.url,
            })
        response = JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_skus': context})
        return response


"""
            {
                sku_id: {'count': 1, 'selected': True}
                sku_id: {'count': 1, 'selected': True}
                sku_id: {'count': 1, 'selected': True} 
            }
"""