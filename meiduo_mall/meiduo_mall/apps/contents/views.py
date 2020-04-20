from django.shortcuts import render
from django.views import View
from .utils import get_category
from .models import ContentCategory


# Create your views here.
class IndexView(View):

    def get(self, request):
        """
        {
        'lb': [],
        'kx':[],
        }
        """
        contents = {}
        # 查询所有广告分类模型集合
        contents_cats_qs = ContentCategory.objects.all()
        # 遍历所有广告分类模型集合
        for contents_cats_model in contents_cats_qs:
            # 过滤查询广告分类模型对应的广告信息集合
            contents_qs = contents_cats_model.content_set.filter(status=True).order_by('sequence')
            # 添加广告分类和广告信息至自带那种
            contents[contents_cats_model.key] = contents_qs

        context = {
            'categories': get_category(),   # 商品类别渲染
            'contents': contents,   # 商品广告渲染
        }
        return render(request, 'index.html', context)


# def goods_category():
#
#     """
#      {
#         group_id: {channels: [], sub_cats: []}
#      }
#     """
#     categories = {}
#     # 获取商品频道分类查询集
#     channel_qs = GoodsChannel.objects.order_by('group_id', 'sequence')
#     for channel_model in channel_qs:
#         # 获取频道分类模型的group_id
#         group_id = channel_model.group_id
#         if group_id not in categories:
#             categories['group_id'] = {'channels': [], 'sub_cats': []}
#         cat1 = channel_model.category
#         cat1.url = channel_model.url
#         categories['group_id']['channels'].append(cat1)
#
#
#     # 渲染模板内容
#     content = {
#         # 商品分类
#         'category': categories,
#
#     }
#     return content
