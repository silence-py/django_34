from django.shortcuts import render
from django.views import View
from django.http import HttpResponseForbidden, JsonResponse
from django.core.paginator import Paginator, EmptyPage
from django.utils import timezone
from django_redis import get_redis_connection
import json
# Create your views here.

from .utils import get_bread_crumb
from .models import GoodsCategory, SKU, GoodVisitCount
from contents.utils import get_category
from meiduo_mall.utils.response_code import RETCODE
from meiduo_mall.utils.views import LoginRequiredView


class ListView(View):

    def get(self, request, category_id, page_num):
        page_num = int(page_num)

        try:
            # 获取三级类别模型对象
            category_model = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return render(request, '404.html')
        # 通过是否含有下级类别来判断是否为三级类别
        sub_cat = category_model.subs.all()
        if sub_cat:
            return render(request, '404.html')
        # 获取查询参数中的排序方式, 用户如果未指定则按照默认方式
        sort = request.GET.get('sort', 'default')

        # 按照价格字段排序
        if sort == 'price':
            sort_field = 'price'
        # 按照销量字段排序
        elif sort == 'hot':
            sort_field = '-sales'
        else:
            # 默认按照创建时间排序
            sort_field = 'create_time'
        # 每页展示的商品数量
        page = 5
        # 获取当前三级类别下的所有sku查询集
        sku_qs = category_model.sku_set.filter(category=category_model, is_launched=True).order_by(sort_field)
        # 当前三级类别下的所有sku数量
        sku_num = sku_qs.count()
        # 分页展示的页面总数量
        # total_page = sku_num // page + 1 if sku_num % page else 0
        # page_sku = sku_qs[0:5]
        # page_sku = sku_qs[5:10]
        # page_sku = sku_qs[10:15]
        # 利用切片获取当前页面要展示的sku
        # page_sku = sku_qs[(page_num-1) * page: page*page_num]

        # 创建分页器对象
        paginator = Paginator(sku_qs, page)
        try:
            # 分页器筛选当前页面要展示的sku
            page_sku = paginator.page(page_num)
        except EmptyPage:
            return HttpResponseForbidden('empty page')

        # 分页展示的页面总数量
        total_page = paginator.num_pages

        context = {
            'categories': get_category(),   # 频道分类
            'breadcrumb': get_bread_crumb(category_model),   # 面包屑导航
            'category': category_model,   # 三级类别模型
            'page_skus': page_sku,   # 分页后商品sku
            'page_num': page_num,   # 当前页码
            'total_page': total_page,   # 总页数
            'sort': sort,   # 排序方式
        }
        return render(request, 'list.html', context)


class HotGoodsView(View):
    def get(self, request, category_id):

        try:
            category_model = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return HttpResponseForbidden("参数错误")
        # 通过是否含有下级类别来判断是否为三级类别
        sub_cat = category_model.subs.all()
        if sub_cat:
            return HttpResponseForbidden("参数错误")
        hot_sku_qs = category_model.sku_set.filter(category=category_model, is_launched=True).order_by('-sales')
        hot_sku = hot_sku_qs[0:2]
        context = []
        for sku in hot_sku:
            context.append(
                {
                    'id': sku.id,
                    'default_image_url': sku.default_image.url,
                    'name': sku.name,
                    'price': sku.price
                }
            )

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'hot_skus': context})


class DetailsGoodsView(View):
    def get(self, request, sku_id):
        try:
            sku_model = SKU.objects.get(id=sku_id, is_launched=True)
        except SKU.DoesNotExist:
            return HttpResponseForbidden("参数错误")

        category_model = sku_model.category

        spu = sku_model.spu

        """1.准备当前商品的规格选项列表 [8, 11]"""
        # 获取出当前正显示的sku商品的规格选项id列表
        current_sku_spec_qs = sku_model.specs.order_by('spec_id')
        current_sku_option_ids = []  # [8, 11]
        for current_sku_spec in current_sku_spec_qs:
            current_sku_option_ids.append(current_sku_spec.option_id)

        """2.构造规格选择仓库
        {(8, 11): 3, (8, 12): 4, (9, 11): 5, (9, 12): 6, (10, 11): 7, (10, 12): 8}
        """
        # 构造规格选择仓库
        temp_sku_qs = spu.sku_set.all()  # 获取当前spu下的所有sku
        # 选项仓库大字典
        spec_sku_map = {}  # {(8, 11): 3, (8, 12): 4, (9, 11): 5, (9, 12): 6, (10, 11): 7, (10, 12): 8}
        for temp_sku in temp_sku_qs:
            # 查询每一个sku的规格数据
            temp_spec_qs = temp_sku.specs.order_by('spec_id')
            temp_sku_option_ids = []  # 用来包装每个sku的选项值
            for temp_spec in temp_spec_qs:
                temp_sku_option_ids.append(temp_spec.option_id)
            spec_sku_map[tuple(temp_sku_option_ids)] = temp_sku.id

        """3.组合 并找到sku_id 绑定"""
        spu_spec_qs = spu.specs.order_by('id')  # 获取当前spu中的所有规格

        for index, spec in enumerate(spu_spec_qs):  # 遍历当前所有的规格
            spec_option_qs = spec.options.all()  # 获取当前规格中的所有选项
            temp_option_ids = current_sku_option_ids[:]  # 复制一个新的当前显示商品的规格选项列表
            for option in spec_option_qs:  # 遍历当前规格下的所有选项
                temp_option_ids[index] = option.id  # [8, 12]
                option.sku_id = spec_sku_map.get(tuple(temp_option_ids))  # 给每个选项对象绑定下他sku_id属性

            spec.spec_options = spec_option_qs  # 把规格下的所有选项绑定到规格对象的spec_options属性上

        # 查询sku关联的所有商品订单信息
        order_goods = sku_model.ordergoods_set.filter(is_commented=True).order_by('-create_time')

        context = {
            'categories': get_category(),
            'breadcrumb': get_bread_crumb(category_model),
            'sku': sku_model,
            'spu': spu,
            'order_goods': order_goods,
            'category': category_model,
            'spec_qs': spu_spec_qs,  # 当前商品的所有规格数据
        }
        return render(request, 'detail.html', context)


class GoodVisitView(View):
    """商品访问量统计"""
    def post(self, request, category_id):
        # 校验
        try:
            # 获取三级类别模型对象
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return HttpResponseForbidden("参数错误")

        # 判断当前类别是否为三级类别
        if category.subs.all():
            return HttpResponseForbidden("参数错误")

        # 获取当前计算机的日期
        # date = timezone.localdate()
        date = timezone.now()
        # 查询当前商品类别今日是否访问过
        try:
            # 已访问商品类别直接访问量计数加1
            good_visit = GoodVisitCount.objects.get(category=category, date=date)
        except GoodVisitCount.DoesNotExist:
            # 未访问商品类别新增记录并将访问量计数加1
            good_visit = GoodVisitCount(category=category)


        good_visit.count += 1
        good_visit.save()
        # 响应Json数据
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

