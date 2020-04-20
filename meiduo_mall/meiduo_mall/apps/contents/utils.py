from goods.models import GoodsCategory, GoodsChannel


def get_category():
    """
    {
        '组号': {'channels': [], 'sub_cats': []}
        '组号': {'channels': [], 'sub_cats': []}
    }
    """
    # 商品类别字典
    categories = {}

    # 按照group_id和sequence对频道进行排序
    channel_qs = GoodsChannel.objects.order_by('group_id', 'sequence')

    for channel_model in channel_qs:
        # 获取商品频道模型的组号
        group_id = channel_model.group_id
        # categories[group_id] = {'channels': [], 'sub_cats': []}
        # 判断组号是否存在
        # if group_id in categories:
        #     categories[group_id] = {'channels': [], 'sub_cats': []}
        categories.setdefault(group_id, {'channels': [], 'sub_cats': []})
        # 通过外键获取一级商品类别模型
        cat1 = channel_model.category

        # 将一级频道模型的url添加到一级分类模型的url中
        cat1.url = channel_model.url
        # 向商品类别字典追加一级类别模型
        categories[group_id]['channels'].append(cat1)

        # 获取一级分类模型下的所有二级分类模型
        cat2_qs = cat1.subs.all()

        for cat2_model in cat2_qs:
            # 获取二级分类模型下的所有三级模型
            cat3_qs = cat2_model.subs.all()
            # 将三级分类模型存储至二级分类模型下的sub_cats属性中
            cat2_model.sub_cats = cat3_qs
            # 向商品类别字典追加二级类别模型
            categories[group_id]['sub_cats'].append(cat2_model)

    return categories
