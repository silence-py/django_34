import time
import os
from django.template import loader
from django.conf import settings

from .utils import get_category
from .models import ContentCategory

# from contents.crons import generate_static_index_html


def generate_static_index_html():
    """
    生成静态的主页html文件
    """
    print('%s: generate_static_index_html' % time.ctime())
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
        'categories': get_category(),  # 商品类别渲染
        'contents': contents,  # 商品广告渲染
    }

    # 获取首页模板文件
    template = loader.get_template('index.html')
    # 渲染首页html字符串
    html_text = template.render(context)
    # 将首页html字符串写入到指定目录，命名'index.html'
    file_path = os.path.join(settings.STATICFILES_DIRS[0], 'index.html')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_text)
