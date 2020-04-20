# celery 启动文件
from celery import Celery
import os

# 使用django配置环境模板
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meiduo_mall.settings.dev")

# 实例化celery对象
celery_app = Celery('meiduo')

# 指定任务仓库
celery_app.config_from_object('celery_tasks.config')

# 执行哪些任务
celery_app.autodiscover_tasks(['celery_tasks.sms', 'celery_tasks.email'])
