from django.db import models


class BaseModel(models.Model):

    """创建模型类基类并添加字段"""
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        abstract = True   # 说明时抽象模型类, 用于继承使用, 迁移建表时不会生成表格
