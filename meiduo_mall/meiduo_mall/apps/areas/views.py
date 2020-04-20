from django.shortcuts import render
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseForbidden

from meiduo_mall.utils.views import LoginRequiredView
from meiduo_mall.utils.response_code import RETCODE
from .models import Area


# Create your views here.
class AreaView(LoginRequiredView):

    def get(self, request):
        # 接收数据
        area_id = request.GET.get('area_id')

        # 判断是否为空
        if area_id is None:
            province_list = cache.get('province_list')
            if province_list is None:
                # 获取省份查询集
                province_model_list = Area.objects.filter(parent_id=None)

                # 创建空列表存储省份ID和名称
                province_list = []

                # 遍历省份查询集, 并向空列表中追加省份字典数据
                for province_model in province_model_list:
                    province_list.append({'id': province_model.id, 'name': province_model.name})

                cache.set('province_list', province_list, 3600)

                # 响应JSON数据
            return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'province_list': province_list})

        else:
            # 查询对应市/区
            try:
                sub_data = cache.get(area_id)

                if sub_data is None:
                    # 查询父类模型
                    parent_model = Area.objects.get(id=area_id)

                    # 通过外键查询父类模型下的所有子模型
                    sub_model_list = parent_model.subs.all()

                    sub_list = []

                    for sub_model in sub_model_list:
                        sub_list.append({'id': sub_model.id, 'name': sub_model.name})

                    sub_data = {
                        'id': parent_model.id,
                        'name': parent_model.name,
                        'subs': sub_list
                    }

                    cache.set(area_id, sub_data, 3600)

                return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'sub_data': sub_data})

            except Area.DoesNotExist:
                return HttpResponseForbidden('查询失败')

