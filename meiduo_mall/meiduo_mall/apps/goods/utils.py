

def get_bread_crumb(category_model):
    """包装面包屑导航"""
    bread_crumb = {}
    # 获取三级类别模型并添加至字典
    bread_crumb['cat3'] = category_model
    # 获取二级类别模型并添加至字典
    bread_crumb['cat2'] = category_model.parent
    # 获取一级类别模型
    cat1 = category_model.parent.parent
    # 将频道url存储值一级类别模型url属性中
    cat1.url = cat1.goodschannel_set.all()[0].url
    bread_crumb['cat1'] = cat1

    return bread_crumb
