import pickle, base64
from django_redis import get_redis_connection


def merge_cart_cookie_to_redis(request, response):
    # 获取cookie中的购物车数据
    user = request.user
    cart_str = request.COOKIES.get('carts')
    # 如果cookie中没有购物车数据直接返回
    if not cart_str:
        return
    # {sku_id: {'count':1, 'selected': True}
    # 如果cookie中有数据转换为字典格式
    cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
    # 链接redis数据库
    redis_cli = get_redis_connection('carts')
    pl = redis_cli.pipeline()
    # 遍历cookie中购物车字典获取所有sku_id
    for sku_id in cart_dict:
        # 将sku购物车信息添加至redis数据库
        pl.hset('cart_%s' % user.id, sku_id, cart_dict[sku_id]['count'])
        if cart_dict[sku_id]['selected']:
            pl.sadd('selected_%s' % user.id, sku_id)
        else:
            pl.srem('selected_%s' % user.id, sku_id)
    # 执行管道
    pl.execute()
    # 完成合并后将cookie中的数据清空
    response.delete_cookie('carts')
